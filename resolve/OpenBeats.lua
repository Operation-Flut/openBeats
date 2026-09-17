-- OpenBeats for DaVinci Resolve 21.1+ Free and Studio.
--
-- Resolve Free keeps all Resolve interaction inside Lua. UIManager is not used.
-- Track selection and beat settings are requested through a tiny DRT trigger and
-- shown by the external OpenBeats Kivy window. Beat analysis uses a scriptable
-- MP4/AAC render because current Resolve builds can expose Wave/wav without an
-- API-selectable codec.

local function resolveGlobal(name)
    local value = rawget(_G, name)
    if value == nil then return nil end
    if type(value) == "function" then
        local ok, result = pcall(value)
        if ok then return result end
        return nil
    end
    return value
end

local resolveHost = resolveGlobal("resolve") or resolveGlobal("Resolve")
local fusionHost = resolveGlobal("fusion") or resolveGlobal("fu") or resolveGlobal("app")
local bmdHost = resolveGlobal("bmd")

if fusionHost == nil and resolveHost ~= nil then
    local ok, value = pcall(function() return resolveHost:Fusion() end)
    if ok then fusionHost = value end
end
if fusionHost == nil then fusionHost = resolveGlobal("Fusion") end

local stageKey = "OpenBeats.LauncherStage"
local errorKey = "OpenBeats.LauncherError"

local function setData(key, value)
    if fusionHost == nil then return false end
    local ok = pcall(function() fusionHost:SetData(key, value) end)
    return ok
end

local function setStage(stage)
    local value = tostring(stage)
    setData(stageKey, value)
    if type(print) == "function" then
        pcall(print, "[OpenBeats] " .. value)
    end
end

local function safePrint(message)
    if type(print) == "function" then
        pcall(print, "[OpenBeats] " .. tostring(message))
    end
end

local function waitBriefly()
    if bmdHost ~= nil then
        local ok = pcall(function() bmdHost.wait(0.10) end)
        if ok then return end
    end
    if os ~= nil and type(os.clock) == "function" then
        local started = os.clock()
        while os.clock() - started < 0.10 do end
    end
end

local function getEnv(name)
    if os ~= nil and type(os.getenv) == "function" then
        local ok, value = pcall(os.getenv, name)
        if ok and value ~= nil and value ~= "" then return value end
    end
    if fusionHost ~= nil then
        local ok, value = pcall(function() return fusionHost:GetEnv(name) end)
        if ok and value ~= nil and value ~= "" then return value end
    end
    return nil
end

local function fail(message)
    local text = tostring(message)
    setData(errorKey, text)
    setStage("failed: " .. text)
    error("OpenBeats: " .. text)
end

local function asNumber(value, fallback)
    if value == nil then return fallback end
    local cleaned = string.gsub(tostring(value), ",", ".")
    return tonumber(cleaned) or fallback
end

local function lowerExtension(value)
    return string.lower(string.gsub(tostring(value or ""), "^%.", ""))
end

local function getSetting(project, timeline, name, fallback)
    local ok, value = pcall(function() return timeline:GetSetting(name) end)
    if ok and value ~= nil and tostring(value) ~= "" then return value end
    ok, value = pcall(function() return project:GetSetting(name) end)
    if ok and value ~= nil and tostring(value) ~= "" then return value end
    return fallback
end

local function resolveVersionSupported()
    if resolveHost == nil then return false, "Resolve application object is unavailable." end
    local ok, version = pcall(function() return resolveHost:GetVersionString() end)
    if not ok or version == nil then return false, "Could not determine the Resolve version." end
    local major, minor = string.match(tostring(version), "^(%d+)%.(%d+)")
    major = tonumber(major)
    minor = tonumber(minor)
    if major == nil or minor == nil then
        return false, "Could not parse Resolve version " .. tostring(version) .. "."
    end
    if major < 21 or (major == 21 and minor < 1) then
        return false, "OpenBeats requires DaVinci Resolve 21.1 or newer."
    end
    return true, tostring(version)
end

local function sessionNonce()
    local timestamp = "notime"
    if os ~= nil and type(os.time) == "function" then
        local ok, value = pcall(os.time)
        if ok and value ~= nil then timestamp = tostring(value) end
    end
    local entropy = string.gsub(tostring({}), "[^A-Za-z0-9]", "")
    if #entropy > 14 then entropy = string.sub(entropy, #entropy - 13) end
    if #entropy < 4 then entropy = "session" end
    return timestamp .. "-" .. entropy
end

local function trackItems(timeline, trackIndex)
    local ok, value = pcall(function()
        return timeline:GetItemListInTrack("audio", trackIndex)
    end)
    if ok and type(value) == "table" then return value end
    return {}
end

local function populatedAudioTracks(timeline)
    local count = tonumber(timeline:GetTrackCount("audio")) or 0
    if count < 1 then error("The current timeline has no audio tracks.") end

    local tracks = {}
    for index = 1, count do
        local items = trackItems(timeline, index)
        if #items > 0 then
            table.insert(tracks, { index = index, itemCount = #items })
        end
    end
    if #tracks < 1 then error("The current timeline has no audio clips to analyze.") end
    return tracks
end

local function analysisRange(timeline, trackIndex)
    local items = trackItems(timeline, trackIndex)
    local first = nil
    local last = nil
    for _, item in pairs(items) do
        local startOk, startValue = pcall(function() return item:GetStart() end)
        local endOk, endValue = pcall(function() return item:GetEnd() end)
        if startOk and endOk then
            local startFrame = math.floor(asNumber(startValue, 0))
            local endFrame = math.floor(asNumber(endValue, 0))
            if endFrame > startFrame then
                if first == nil or startFrame < first then first = startFrame end
                if last == nil or endFrame > last then last = endFrame end
            end
        end
    end
    if first == nil or last == nil or last <= first then
        error("The selected audio track has no renderable clips.")
    end
    return first, last
end

local function preferredCodec(codecs)
    local fallback = nil
    for codecName, codecId in pairs(codecs or {}) do
        local id = tostring(codecId or "")
        if id ~= "" then
            if fallback == nil then fallback = id end
            local lowered = string.lower(tostring(codecName) .. " " .. id)
            if string.find(lowered, "h264", 1, true) or
               string.find(lowered, "h.264", 1, true) then
                return id
            end
        end
    end
    return fallback
end

local function pickScriptableContainer(project)
    local formats = project:GetRenderFormats() or {}
    for _, wanted in ipairs({ "mp4", "mov" }) do
        for _, formatId in pairs(formats) do
            local normalized = lowerExtension(formatId)
            if normalized == wanted then
                local codecs = project:GetRenderCodecs(tostring(formatId)) or {}
                local codecId = preferredCodec(codecs)
                if codecId ~= nil then
                    return tostring(formatId), tostring(codecId), normalized
                end
            end
        end
    end
    error("Resolve exposes no scriptable MP4/QuickTime renderer for OpenBeats.")
end

local function renderTrack(project, timeline, trackIndex, startFrame, endFrame, targetDir, customName, fps)
    local presetName = "__OpenBeats_" .. sessionNonce()
    local temporaryTimeline = nil
    local jobId = nil
    local savedPreset = false
    local originalTimeline = timeline
    local originalPage = nil

    pcall(function() originalPage = resolveHost:GetCurrentPage() end)

    local function cleanup()
        setStage("render-cleanup")
        if jobId ~= nil then pcall(function() project:DeleteRenderJob(jobId) end) end
        pcall(function() project:SetCurrentTimeline(originalTimeline) end)
        if temporaryTimeline ~= nil then
            pcall(function() project:GetMediaPool():DeleteTimelines({ temporaryTimeline }) end)
        end
        if savedPreset then
            pcall(function()
                project:LoadRenderPreset(presetName)
                project:DeleteRenderPreset(presetName)
            end)
        end
        if originalPage ~= nil and tostring(originalPage) ~= "" then
            pcall(function() resolveHost:OpenPage(tostring(originalPage)) end)
        end
    end

    local ok, renderError = pcall(function()
        setStage("render-snapshot")
        savedPreset = project:SaveAsNewRenderPreset(presetName) == true
        if not savedPreset then
            error("Resolve could not snapshot the current render settings.")
        end

        setStage("render-isolate-track")
        temporaryTimeline = timeline:DuplicateTimeline("__OpenBeats Audio Export")
        if temporaryTimeline == nil then error("Resolve could not duplicate the timeline.") end
        if project:SetCurrentTimeline(temporaryTimeline) == false then
            error("Resolve could not activate the temporary OpenBeats timeline.")
        end

        local videoCount = tonumber(temporaryTimeline:GetTrackCount("video")) or 0
        for index = 1, videoCount do
            temporaryTimeline:SetTrackEnable("video", index, false)
        end
        local audioCount = tonumber(temporaryTimeline:GetTrackCount("audio")) or 0
        for index = 1, audioCount do
            temporaryTimeline:SetTrackEnable("audio", index, index == trackIndex)
        end

        setStage("render-format")
        local formatId, codecId = pickScriptableContainer(project)
        if project:SetCurrentRenderFormatAndCodec(formatId, codecId) == false then
            error(
                "Resolve rejected the scriptable render format " ..
                tostring(formatId) .. "/" .. tostring(codecId) .. "."
            )
        end
        if project:SetCurrentRenderMode(1) == false then
            error("Resolve rejected Single Clip render mode.")
        end

        setStage("render-settings")
        if project:SetRenderSettings({
            SelectAllFrames = false,
            MarkIn = startFrame,
            MarkOut = endFrame - 1,
            TargetDir = targetDir,
            CustomName = customName,
            UseUniqueFilenames = false,
            ExportVideo = true,
            ExportAudio = true,
            FormatWidth = 256,
            FormatHeight = 144,
            FrameRate = fps,
            AudioCodec = "aac",
            AudioSampleRate = 48000,
        }) == false then
            error("Resolve rejected the OpenBeats analysis render settings.")
        end

        setStage("render-job")
        jobId = project:AddRenderJob()
        if jobId == nil or jobId == "" then
            error("Resolve could not create the OpenBeats analysis render job.")
        end

        setStage("rendering")
        if project:StartRendering({ jobId }, false) == false then
            error("Resolve could not start the OpenBeats analysis render.")
        end

        local iterations = 0
        while project:IsRenderingInProgress() do
            iterations = iterations + 1
            if iterations > 108000 then
                pcall(function() project:StopRendering() end)
                error("OpenBeats analysis render timed out.")
            end
            waitBriefly()
        end

        setStage("render-status")
        local status = project:GetRenderJobStatus(jobId) or {}
        local jobStatus = tostring(status.JobStatus or status["JobStatus"] or "")
        if jobStatus ~= "Complete" then
            local detail = tostring(status.Error or status["Error"] or jobStatus or "unknown render error")
            error("OpenBeats analysis render failed: " .. detail)
        end
    end)

    cleanup()
    if not ok then error(renderError) end
end

local function waitForResponse(path, description)
    local iterations = 0
    while true do
        local ok, value = pcall(dofile, path)
        if ok and type(value) == "table" and value.status ~= nil then return value end
        iterations = iterations + 1
        if iterations > 6000 then
            error("Timed out waiting for the OpenBeats " .. tostring(description) .. ".")
        end
        waitBriefly()
    end
end

local function trackIsAllowed(tracks, trackIndex)
    for _, entry in ipairs(tracks) do
        if entry.index == trackIndex then return true end
    end
    return false
end

local function chooseAudioTrack(timeline, tracks, exchangeDir, sessionDir, sessionId)
    local indices = {}
    for _, entry in ipairs(tracks) do table.insert(indices, tostring(entry.index)) end
    local triggerPath = exchangeDir .. "\\OpenBeatsSelect_" .. sessionId ..
        "__" .. table.concat(indices, "-") .. ".drt"

    setStage("settings-request")
    local exportOk, exportResult = pcall(function()
        return timeline:Export(triggerPath, resolveHost.EXPORT_DRT, resolveHost.EXPORT_NONE)
    end)
    if not exportOk or exportResult == false then
        error("Resolve could not create the OpenBeats settings trigger.")
    end

    setStage("settings-wait")
    local selection = waitForResponse(sessionDir .. [[\selection.lua]], "beat settings")
    if tostring(selection.status) == "cancelled" then return nil end
    if tostring(selection.status) ~= "ok" then
        error("Beat settings failed: " .. tostring(selection.message or "unknown error"))
    end

    local trackIndex = math.floor(asNumber(selection.track, 0))
    if not trackIsAllowed(tracks, trackIndex) then
        error("The OpenBeats settings window returned an invalid audio track selection.")
    end
    return trackIndex
end

local function markerCustomData(timeline, frameId, marker)
    if type(marker) == "table" then
        local value = marker.customData or marker["customData"]
        if value ~= nil and tostring(value) ~= "" then return tostring(value) end
    end
    local ok, value = pcall(function() return timeline:GetMarkerCustomData(frameId) end)
    if ok and value ~= nil then return tostring(value) end
    return ""
end

local function clearOpenBeatsMarkers(timeline, startFrame, endFrame, timelineStart)
    local markers = timeline:GetMarkers() or {}
    local remove = {}
    for frameId, marker in pairs(markers) do
        local offset = asNumber(frameId, nil)
        if offset ~= nil then
            local absolute = timelineStart + offset
            local customData = markerCustomData(timeline, frameId, marker)
            if absolute >= startFrame and absolute < endFrame and
               string.sub(customData, 1, 17) == "openbeats.beat.v1" then
                table.insert(remove, frameId)
            end
        end
    end
    for _, frameId in ipairs(remove) do
        pcall(function() timeline:DeleteMarkerAtFrame(frameId) end)
    end
    return #remove
end

local function placeMarkers(timeline, analysis, startFrame, endFrame, fps)
    local timelineStart = math.floor(asNumber(timeline:GetStartFrame(), 0))
    clearOpenBeatsMarkers(timeline, startFrame, endFrame, timelineStart)

    local beats = analysis.beats or {}
    local bpm = asNumber(analysis.bpm, 0)
    local note = bpm > 0 and string.format("%.2f BPM", bpm) or "Beat"
    local usedFrames = {}
    local inserted = 0
    local skipped = 0

    for _, beatSeconds in ipairs(beats) do
        local seconds = asNumber(beatSeconds, -1)
        if seconds >= 0 then
            local absoluteFrame = startFrame + math.floor(seconds * fps + 0.5)
            if absoluteFrame >= startFrame and absoluteFrame < endFrame then
                local markerFrame = absoluteFrame - timelineStart
                if usedFrames[markerFrame] == nil then
                    usedFrames[markerFrame] = true
                    local ok, added = pcall(function()
                        return timeline:AddMarker(
                            markerFrame,
                            "Blue",
                            "Beat",
                            note,
                            1,
                            "openbeats.beat.v1"
                        )
                    end)
                    if ok and added ~= false then inserted = inserted + 1
                    else skipped = skipped + 1 end
                end
            end
        end
    end
    return inserted, skipped
end

local function heartbeatIsFresh(heartbeat)
    if type(heartbeat) ~= "table" then return false end
    local timestamp = asNumber(heartbeat.timestamp, 0)
    if timestamp <= 0 then return false end
    if os == nil or type(os.time) ~= "function" then return true end
    local ok, now = pcall(os.time)
    if not ok or now == nil then return true end
    return math.abs(asNumber(now, 0) - timestamp) <= 15
end

local function run()
    setData(errorKey, nil)
    setStage("start")

    local supported, versionOrError = resolveVersionSupported()
    if not supported then error(versionOrError) end
    safePrint("Resolve version " .. tostring(versionOrError))

    setStage("project-context")
    local manager = resolveHost:GetProjectManager()
    local project = manager and manager:GetCurrentProject() or nil
    if project == nil then error("Open a Resolve project before starting OpenBeats.") end
    local timeline = project:GetCurrentTimeline()
    if timeline == nil then error("Open a timeline before starting OpenBeats.") end

    local fps = asNumber(
        getSetting(
            project,
            timeline,
            "timelineFrameRate",
            getSetting(project, timeline, "timelinePlaybackFrameRate", 24)
        ),
        24
    )
    if fps <= 0 then error("The timeline frame rate is invalid.") end

    local localData = getEnv("LOCALAPPDATA")
    if localData == nil then error("LOCALAPPDATA is unavailable in Resolve.") end

    setStage("agent-check")
    local heartbeatOk, heartbeat = pcall(dofile, localData .. [[\OpenBeats\agent.lua]])
    if not heartbeatOk or not heartbeatIsFresh(heartbeat) then
        error("The OpenBeats agent is not running or its heartbeat is stale. Start the agent and run OpenBeats again.")
    end

    local sessionId = sessionNonce()
    local exchangeDir = localData .. [[\OpenBeats\Exchange]]
    local sessionDir = localData .. [[\OpenBeats\Sessions\]] .. sessionId
    local tracks = populatedAudioTracks(timeline)
    local trackIndex = chooseAudioTrack(timeline, tracks, exchangeDir, sessionDir, sessionId)
    if trackIndex == nil then
        setStage("cancelled")
        return
    end

    local startFrame, endFrame = analysisRange(timeline, trackIndex)
    local customName = "OpenBeats_" .. sessionId
    local resultPath = sessionDir .. [[\result.lua]]

    setStage("analysis-render")
    safePrint(
        "Analyzing A" .. tostring(trackIndex) .. " frames " ..
        tostring(startFrame) .. "-" .. tostring(endFrame)
    )
    renderTrack(project, timeline, trackIndex, startFrame, endFrame, exchangeDir, customName, fps)

    setStage("waiting-analysis")
    local response = waitForResponse(resultPath, "beat analysis")
    if tostring(response.status) ~= "ok" then
        error("Beat analysis failed: " .. tostring(response.message or "unknown analysis error"))
    end

    setStage("placing-markers")
    local inserted, skipped = placeMarkers(timeline, response, startFrame, endFrame, fps)
    local message = "Generated " .. tostring(inserted) .. " beat markers"
    local bpm = asNumber(response.bpm, 0)
    if bpm > 0 then message = message .. string.format(" at approximately %.2f BPM", bpm) end
    if skipped > 0 then
        message = message .. "; skipped " .. tostring(skipped) .. " occupied positions"
    end
    safePrint(message .. ".")
    setStage("completed: " .. tostring(inserted) .. " markers")
end

local ok, runError = pcall(run)
if not ok then fail(runError) end
