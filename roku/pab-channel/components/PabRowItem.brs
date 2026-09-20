sub init()
    m.rowBg = m.top.findNode("rowBg")
    m.nameLabel = m.top.findNode("nameLabel")
    m.raceLabel = m.top.findNode("raceLabel")
    m.callUpLabel = m.top.findNode("callUpLabel")
    m.startLabel = m.top.findNode("startLabel")
    m.countdownLabel = m.top.findNode("countdownLabel")
    m.resultLabel = m.top.findNode("resultLabel")
end sub

sub onContentChanged()
    item = m.top.itemContent
    if item = invalid then return

    m.nameLabel.text = safeStr(item.name)
    m.raceLabel.text = safeStr(item.race)
    m.callUpLabel.text = safeStr(item.call_up)
    m.startLabel.text = safeStr(item.start_display)
    m.countdownLabel.text = safeStr(item.countdown_display)
    m.resultLabel.text = safeStr(item.result_display)

    status = LCase(safeStr(item.status))
    isNext = (safeStr(item.is_next) = "true")
    daylight = (LCase(safeStr(item.theme)) = "daylight")

    if daylight
        rowDefault = "0x161616FF"
        rowPast = "0x0B0B0BFF"
        rowLive = "0x12301FFF"
        rowNext = "0x2A2208FF"
        textPrimary = "0xFFFFFFFF"
        textSecondary = "0xE5E5E5FF"
        textDim = "0x9CA3AFFF"
        countdown = "0xFFFFFFFF"
        nextAccent = "0xF5C518FF"
        liveAccent = "0x3DFF8AFF"
        result = "0x3DFF8AFF"
    else
        rowDefault = "0x111C33FF"
        rowPast = "0x0F172AFF"
        rowLive = "0x163B2CFF"
        rowNext = "0x1A3A52FF"
        textPrimary = "0xFFFFFFFF"
        textSecondary = "0xE2E8F0FF"
        textDim = "0x64748BFF"
        countdown = "0xF8FAFCFF"
        nextAccent = "0x38BDF8FF"
        liveAccent = "0x4ADE80FF"
        result = "0x22C55EFF"
    end if

    m.rowBg.color = rowDefault
    m.nameLabel.color = textPrimary
    m.raceLabel.color = textSecondary
    m.callUpLabel.color = textSecondary
    m.startLabel.color = textSecondary
    m.countdownLabel.color = countdown
    m.resultLabel.color = result

    if status = "past"
        m.rowBg.color = rowPast
        m.nameLabel.color = textDim
        m.raceLabel.color = textDim
        m.callUpLabel.color = textDim
        m.startLabel.color = textDim
        m.countdownLabel.color = textDim
    else if status = "live"
        m.rowBg.color = rowLive
        m.countdownLabel.color = liveAccent
    else if isNext
        m.rowBg.color = rowNext
        m.countdownLabel.color = nextAccent
    end if
end sub

function safeStr(value as dynamic) as string
    if value = invalid then return ""
    return value.ToStr()
end function
