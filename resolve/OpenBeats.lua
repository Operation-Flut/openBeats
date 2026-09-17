-- OpenBeats for DaVinci Resolve 21.1+ Free and Studio.
--
-- Resolve Free keeps all Resolve interaction inside this Lua Utility script.
-- Audio analysis is delegated to the local OpenBeats agent through a rendered
-- WAV file and a tiny result.lua handoff, following the same architecture used
-- by OpenRoto for Resolve Free.

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

local function showDialog(title, message, errorDialog)
    safePrint(tostring(title) .. ": " .. tostring(message))
    if fusionHost == nil or bmdHost == nil then return false end
    local shown = false
    local ok = pcall(function()
        local ui = fusionHost.UIManager
        local disp = bmdHost.UIDispatcher(ui)
        if ui == nil or disp == nil then return end
        local win = disp:AddWindow(
            {
                ID = "OpenBeatsMessage",
                WindowTitle = tostring(title),
                Geometry = { 360, 260, 640, 200 },
            },
            ui:VGroup {
                ui:Label {
                    ID = "Message",
                    Text = tostring(message),
                    WordWrap = true,
                },
                ui:Button { ID = "OK", Text = "OK" },
            }
        )
        if win == nil then return end
        function win.On.OpenBeatsMessage.Close(ev) disp:ExitLoop() end
        function win.On.OK.Clicked(ev) disp:ExitLoop() end
        win:Show()
        shown = true
        disp:RunLoop()
        win:Hide()
    end)
    return ok and shown
end

local function fail(message)
    showDialog("OpenBeats — Error", tostring(message), true)
    error("OpenBeats: " .. tostring(message))
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

local function trackName(timeline, trackIndex)
    local ok, value = pcall(function()
        return timeline:GetTrackName("audio", trackIndex)
    end)
    if ok and value ~= nil and tostring(value) ~= "" then return tostring(value) end
    return "Audio " .. tostring(trackIndex)
end

local function chooseAudioTrack(timeline)
    local count = tonumber(timeline:GetTrackCount("audio")) or 0
    if count < 1 then error("The current timeline has no audio tracks.") end

    local tracks = {}
    local firstNonEmpty = nil
    for index = 1, count do
        local items = trackItems(timeline, index)
        local entry = {
            index = index,
            name = trackName(timeline, index),
            itemCount = #items,
        }
        table.insert(tracks, entry)
        if firstNonEmpty == nil and #items > 0 then firstNonEmpty = #tracks end
    end

    if firstNonEmpty == nil then error("The current timeline has no audio clips to analyze.") end

    if fusionHost == nil or bmdHost == nil then
        return tracks[firstNonEmpty].index
    end

    local selected = nil
    local ui = fusionHost.UIManager
    local disp = bmdHost.UIDispatcher(ui)
    if ui == nil or disp == nil then return tracks[firstNonEmpty].index end

    local win = disp:AddWindow(
        {
            ID = "OpenBeatsTrackPicker",
            WindowTitle = "OpenBeats — Generate Beat Markers",
            Geometry = { 360, 220, 620, 220 },
        },
        ui:VGroup {
            ui:Label {
                Text = "Choose the soundtrack/audio track to analyze:",
                WordWrap = true,
            },
            ui:ComboBox { ID = "Track" },
            ui:HGroup {
                ui:Button { ID = "Cancel", Text = "Cancel" },
                ui:Button { ID = "Generate", Text = "Generate Beat Markers" },
            },
        }
    )
    if win == nil then return tracks[firstNonEmpty].index end

    local items = win:GetItems()
    for _, entry in ipairs(tracks) do
        local suffix = entry.itemCount == 1 and " clip" or " clips"
        items.Track:AddItem(
            "A" .. tostring(entry.index) .. " — " .. entry.name ..
            " (" .. tostring(entry.itemCount) .. suffix .. ")"
        )
    end
    items.Track.CurrentIndex = firstNonEmpty - 1

    function win.On.OpenBeatsTrackPicker.Close(ev)
        selected = nil
        disp:ExitLoop()
    end
    function win.On.Cancel.Clicked(ev)
        selected = nil
        disp:ExitLoop()
    end
    function win.On.Generate.Clicked(ev)
        local uiIndex = tonumber(items.Track.CurrentIndex) or 0
        local entry = tracks[uiIndex + 1]
        if entry ~= nil and entry.itemCount > 0 then selected = entry.index end
        disp:ExitLoop()
    end

    win:Show()
    disp:RunLoop()
    win:Hide()
    return selected
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

local function pickWavCodec(project)
    local formats = project:GetRenderFormats() or {}
    for formatName, extension in pairs(formats) do
        if lowerExtension(extension) == "wav" then
            local codecs = project:GetRenderCodecs(extension) or project:GetRenderCodecs(formatName) or {}
            local fallback = nil
            for codecName, codecId in pairs(codecs) do
                if fallback == nil then fallback = codecId end
                local lowered = string.lower(tostring(codecName))
                if string.find(lowered, "pcm", 1, true) or
                   string.find(lowered, "linear", 1, true) then
                    return tostring(extension), codecId
                end
            end
            if fallback ~= nil then return tostring(extension), fallback end
        end
    end
    error("Resolve does not expose a WAV audio renderer on this installation.")
end

local function renderTrack(project, timeline, trackIndex, startFrame, endFrame, targetDir, customName)
    local presetName = "__OpenBeats_" .. sessionNonce()
    local temporaryTimeline = nil
    local jobId = nil
    local savedPreset = false
    local originalTimeline = timeline

    local function cleanup()
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
    end

    local ok, renderError = pcall(function()
        savedPreset = project:SaveAsNewRenderPreset(presetName) == true
        if not savedPreset then
            error("Resolve could not snapshot the current render settings.")
        end

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

        local formatId, codecId = pickWavCodec(project)
        if project:SetCurrentRenderFormatAndCodec(formatId, codecId) == false then
            error("Resolve rejected the WAV format selected by OpenBeats.")
        end
        project:SetCurrentRenderMode(1)
        if project:SetRenderSettings({
            SelectAllFrames = false,
            MarkIn = startFrame,
            MarkOut = endFrame - 1,
            TargetDir = targetDir,
            CustomName = customName,
            UseUniqueFilenames = false,
            ExportVideo = false,
            ExportAudio = true,
        }) == false then
            error("Resolve rejected the OpenBeats audio render settings.")
        end

        jobId = project:AddRenderJob()
        if jobId == nil or jobId == "" then
            error("Resolve could not create the OpenBeats audio render job.")
        end
        if project:StartRendering({ jobId }, false) == false then
            error("Resolve could not start the OpenBeats audio render.")
        end

        local iterations = 0
        while project:IsRenderingInProgress() do
            iterations = iterations + 1
            if iterations > 108000 then
                pcall(function() project:StopRendering() end)
                error("OpenBeats audio export timed out.")
            end
            waitBriefly()
        end

        local status = project:GetRenderJobStatus(jobId) or {}
        local jobStatus = tostring(status.JobStatus or status["JobStatus"] or "")
        if jobStatus ~= "Complete" then
            local detail = tostring(status.Error or status["Error"] or jobStatus or "unknown render error")
            error("OpenBeats audio export failed: " .. detail)
        end
    end)

    cleanup()
    if not ok then error(renderError) end
end

local function waitForResult(resultPath)
    local iterations = 0
    while true do
        local ok, value = pcall(dofile, resultPath)
        if ok and type(value) == "table" and value.status ~= nil then return value end
        iterations = iterations + 1
        if iterations > 36000 then
            error("Timed out waiting for the OpenBeats analysis agent.")
        end
        waitBriefly()
    end
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
                    if ok and added ~= false then
                        inserted = inserted + 1
                    else
                        skipped = skipped + 1
                    end
                end
            end
        end
    end
    return inserted, skipped
end

local function run()
    local supported, versionOrError = resolveVersionSupported()
    if not supported then error(versionOrError) end
    safePrint("Resolve version " .. tostring(versionOrError))

    local manager = resolveHost:GetProjectManager()
    local project = manager and manager:GetCurrentProject() or nil
    if project == nil then error("Open a Resolve project before starting OpenBeats.") end
    local timeline = project:GetCurrentTimeline()
    if timeline == nil then error("Open a timeline before starting OpenBeats.") end

    local trackIndex = chooseAudioTrack(timeline)
    if trackIndex == nil then
        safePrint("Cancelled by user.")
        return
    end

    local startFrame, endFrame = analysisRange(timeline, trackIndex)
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
    local sessionId = sessionNonce()
    local customName = "OpenBeats_" .. sessionId
    local exchangeDir = localData .. [[\OpenBeats\Exchange]]
    local resultPath = localData .. [[\OpenBeats\Sessions\]] .. sessionId .. [[\result.lua]]

    safePrint(
        "Analyzing A" .. tostring(trackIndex) .. " frames " ..
        tostring(startFrame) .. "-" .. tostring(endFrame)
    )
    renderTrack(project, timeline, trackIndex, startFrame, endFrame, exchangeDir, customName)

    local response = waitForResult(resultPath)
    if tostring(response.status) ~= "ok" then
        error("Beat analysis failed: " .. tostring(response.message or "unknown analysis error"))
    end

    local inserted, skipped = placeMarkers(timeline, response, startFrame, endFrame, fps)
    local message = "Generated " .. tostring(inserted) .. " beat markers"
    local bpm = asNumber(response.bpm, 0)
    if bpm > 0 then message = message .. string.format(" at approximately %.2f BPM", bpm) end
    if skipped > 0 then
        message = message .. ". " .. tostring(skipped) .. " marker positions were already occupied."
    else
        message = message .. "."
    end
    showDialog("OpenBeats", message, false)
end

local ok, runError = pcall(run)
if not ok then fail(runError) end
