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

    ' Defaults match kiosk upcoming rows.
    m.rowBg.color = "0x111C33FF"
    m.nameLabel.color = "0xFFFFFFFF"
    m.raceLabel.color = "0xE2E8F0FF"
    m.callUpLabel.color = "0xE2E8F0FF"
    m.startLabel.color = "0xE2E8F0FF"
    m.countdownLabel.color = "0xF8FAFCFF"
    m.resultLabel.color = "0x22C55EFF"

    if status = "past"
        m.rowBg.color = "0x0F172AFF"
        m.nameLabel.color = "0x64748BFF"
        m.raceLabel.color = "0x64748BFF"
        m.callUpLabel.color = "0x64748BFF"
        m.startLabel.color = "0x64748BFF"
        m.countdownLabel.color = "0x64748BFF"
    else if status = "live"
        m.rowBg.color = "0x163B2CFF"
        m.countdownLabel.color = "0x4ADE80FF"
    else if isNext
        m.rowBg.color = "0x1A3A52FF"
        m.countdownLabel.color = "0x38BDF8FF"
    end if
end sub

function safeStr(value as dynamic) as string
    if value = invalid then return ""
    return value.ToStr()
end function
