sub init()
    m.titleLabel = m.top.findNode("titleLabel")
    m.clockLabel = m.top.findNode("clockLabel")
    m.dateLabel = m.top.findNode("dateLabel")
    m.statusLabel = m.top.findNode("statusLabel")
    m.pageLabel = m.top.findNode("pageLabel")
    m.emptyLabel = m.top.findNode("emptyLabel")
    m.scheduleGrid = m.top.findNode("scheduleGrid")
    m.logoPoster = m.top.findNode("logoPoster")
    m.alertOverlay = m.top.findNode("alertOverlay")
    m.alertMessage = m.top.findNode("alertMessage")
    m.alertMeta = m.top.findNode("alertMeta")

    m.baseUrl = ""
    m.logoUrl = ""
    m.pageOffset = 0
    m.pageSize = 12
    m.participants = []
    m.boardFontScale = 100
    m.boardTheme = "classic"

    m.bg = m.top.findNode("bg")
    m.panelBg = m.top.findNode("panelBg")
    m.headerBg = m.top.findNode("headerBg")
    m.alertBg = m.top.findNode("alertBg")
    m.alertCard = m.top.findNode("alertCard")
    m.alertEyebrow = m.top.findNode("alertEyebrow")
    m.hName = m.top.findNode("hName")
    m.hRace = m.top.findNode("hRace")
    m.hCallUp = m.top.findNode("hCallUp")
    m.hStart = m.top.findNode("hStart")
    m.hCountdown = m.top.findNode("hCountdown")
    m.hResult = m.top.findNode("hResult")

    m.pollTimer = createObject("roSGNode", "Timer")
    m.pollTimer.repeat = true
    m.pollTimer.duration = 2
    m.pollTimer.observeField("fire", "onPollTick")
    m.top.appendChild(m.pollTimer)

    m.pageTimer = createObject("roSGNode", "Timer")
    m.pageTimer.repeat = true
    m.pageTimer.duration = 8
    m.pageTimer.observeField("fire", "onPageTick")
    m.top.appendChild(m.pageTimer)

    m.top.observeField("baseUrl", "onBaseUrlChanged")
end sub

sub onBaseUrlChanged()
    m.baseUrl = m.top.baseUrl
    if m.baseUrl = invalid or m.baseUrl = ""
        m.statusLabel.text = "No Pi URL (deep link contentId missing)"
        return
    end if
    m.statusLabel.text = "Connecting…"
    m.pollTimer.control = "start"
    m.pageTimer.control = "start"
    fetchBoard()
end sub

sub onPollTick()
    fetchBoard()
end sub

sub onPageTick()
    if m.participants.Count() <= m.pageSize then return
    m.pageOffset = m.pageOffset + m.pageSize
    if m.pageOffset >= m.participants.Count()
        m.pageOffset = 0
    end if
    renderRows()
end sub

sub fetchBoard()
    if m.baseUrl = invalid or m.baseUrl = "" then return
    url = m.baseUrl
    if Right(url, 1) = "/"
        url = Left(url, Len(url) - 1)
    end if
    url = url + "/api/tv-board"

    task = createObject("roSGNode", "PabFetchTask")
    task.url = url
    task.observeField("response", "onBoardResponse")
    task.observeField("error", "onBoardError")
    task.control = "RUN"
    m.fetchTask = task
end sub

sub onBoardError()
    err = ""
    if m.fetchTask <> invalid
        err = m.fetchTask.error
    end if
    if err = invalid or err = ""
        return
    end if
    m.statusLabel.text = "Reconnect: " + err
    if m.baseUrl <> invalid and m.baseUrl <> ""
        m.statusLabel.text = m.statusLabel.text + " · " + m.baseUrl
    end if
    m.alertOverlay.visible = false
end sub

sub onBoardResponse()
    if m.fetchTask = invalid then return
    raw = m.fetchTask.response
    if raw = invalid or raw = ""
        return
    end if

    parsed = ParseJson(raw)
    if parsed = invalid
        m.statusLabel.text = "Bad JSON from Pi"
        return
    end if

    if parsed.DoesExist("display_title") and parsed.display_title <> invalid
        m.titleLabel.text = parsed.display_title.ToStr()
    end if

    if parsed.DoesExist("kiosk_now") and parsed.kiosk_now <> invalid
        m.clockLabel.text = formatClock12(parsed.kiosk_now.ToStr())
    end if

    if parsed.DoesExist("display_date") and parsed.display_date <> invalid
        m.dateLabel.text = formatPrettyDate(parsed.display_date.ToStr())
    end if

    if parsed.DoesExist("board_theme") and parsed.board_theme <> invalid
        theme = LCase(parsed.board_theme.ToStr())
        if theme <> "daylight"
            theme = "classic"
        end if
        if theme <> m.boardTheme
            m.boardTheme = theme
            applyBoardTheme()
        end if
    end if

    if parsed.DoesExist("logo_url") and parsed.logo_url <> invalid and parsed.logo_url <> ""
        logo = parsed.logo_url.ToStr()
        if logo <> m.logoUrl
            m.logoUrl = logo
            m.logoPoster.uri = logo
            m.logoPoster.visible = true
            m.titleLabel.translation = [140, 28]
            m.dateLabel.translation = [140, 78]
        end if
    else
        m.logoPoster.visible = false
        m.logoUrl = ""
        m.titleLabel.translation = [48, 28]
        m.dateLabel.translation = [48, 78]
    end if

    m.participants = []
    if parsed.DoesExist("participants") and parsed.participants <> invalid
        m.participants = parsed.participants
    end if
    if m.pageOffset >= m.participants.Count()
        m.pageOffset = 0
    end if
    renderRows()

    if parsed.DoesExist("active_alert") and parsed.active_alert <> invalid
        alert = parsed.active_alert
        msg = ""
        meta = ""
        if alert.DoesExist("message") and alert.message <> invalid
            msg = alert.message.ToStr()
        end if
        if alert.DoesExist("name") and alert.name <> invalid
            meta = alert.name.ToStr()
        end if
        if alert.DoesExist("start_time") and alert.start_time <> invalid
            startDisp = formatStartTime(alert.start_time.ToStr())
            if meta <> ""
                meta = meta + " · start " + startDisp
            else
                meta = "start " + startDisp
            end if
        end if
        m.alertMessage.text = msg
        m.alertMeta.text = meta
        m.alertOverlay.visible = (msg <> "")
    else
        m.alertOverlay.visible = false
    end if

    count = m.participants.Count()
    m.statusLabel.text = count.ToStr() + " riders · updated " + m.clockLabel.text

    sec = CreateObject("roRegistrySection", "pab")
    sec.Write("baseUrl", m.baseUrl)
    sec.Flush()
end sub

sub renderRows()
    content = createObject("roSGNode", "ContentNode")

    if m.participants.Count() = 0
        m.scheduleGrid.content = content
        m.emptyLabel.text = "No starts scheduled today."
        m.emptyLabel.visible = true
        m.pageLabel.text = ""
        return
    end if
    m.emptyLabel.visible = false

    nextId = ""
    for i = 0 to m.participants.Count() - 1
        p = m.participants[i]
        if LCase(fieldStr(p, "status")) = "upcoming"
            nextId = fieldStr(p, "id")
            exit for
        end if
    end for

    last = m.pageOffset + m.pageSize - 1
    if last >= m.participants.Count()
        last = m.participants.Count() - 1
    end if

    for i = m.pageOffset to last
        p = m.participants[i]
        isNextStr = "false"
        if fieldStr(p, "id") = nextId
            isNextStr = "true"
        end if
        item = content.createChild("ContentNode")
        item.addFields({
            name: fieldStr(p, "name"),
            race: fieldStr(p, "race"),
            call_up: fieldStr(p, "call_up"),
            start_display: formatStartTime(fieldStr(p, "start_time")),
            countdown_display: formatCountdown(p),
            result_display: formatResult(p),
            status: fieldStr(p, "status"),
            is_next: isNextStr,
            theme: m.boardTheme
        })
    end for

    m.scheduleGrid.content = content

    if m.participants.Count() > m.pageSize
        page = Int(m.pageOffset / m.pageSize) + 1
        pages = Int((m.participants.Count() + m.pageSize - 1) / m.pageSize)
        m.pageLabel.text = "Page " + page.ToStr() + " / " + pages.ToStr()
    else
        m.pageLabel.text = ""
    end if
end sub

sub applyBoardTheme()
    daylight = (m.boardTheme = "daylight")
    if daylight
        bg = "0x0B0B0BFF"
        panel = "0x161616FF"
        header = "0x1F1F1FFF"
        muted = "0xE5E5E5FF"
        dim = "0x9CA3AFFF"
        accent = "0xF5C518FF"
        alertScrim = "0x0B0B0BF0"
        alertCard = "0x121212FF"
        title = "0xFFFFFFFF"
    else
        bg = "0x0F172AFF"
        panel = "0x111C33FF"
        header = "0x152238FF"
        muted = "0x94A3B8FF"
        dim = "0x64748BFF"
        accent = "0x38BDF8FF"
        alertScrim = "0x0F172AE6"
        alertCard = "0x152238FF"
        title = "0xF8FAFCFF"
    end if

    if m.bg <> invalid then m.bg.color = bg
    if m.panelBg <> invalid then m.panelBg.color = panel
    if m.headerBg <> invalid then m.headerBg.color = header
    if m.titleLabel <> invalid then m.titleLabel.color = title
    if m.dateLabel <> invalid then m.dateLabel.color = muted
    if m.clockLabel <> invalid then m.clockLabel.color = accent
    if m.statusLabel <> invalid then m.statusLabel.color = accent
    if m.pageLabel <> invalid then m.pageLabel.color = dim
    if m.emptyLabel <> invalid then m.emptyLabel.color = muted
    if m.hName <> invalid then m.hName.color = muted
    if m.hRace <> invalid then m.hRace.color = muted
    if m.hCallUp <> invalid then m.hCallUp.color = muted
    if m.hStart <> invalid then m.hStart.color = muted
    if m.hCountdown <> invalid then m.hCountdown.color = muted
    if m.hResult <> invalid then m.hResult.color = muted
    if m.alertBg <> invalid then m.alertBg.color = alertScrim
    if m.alertCard <> invalid then m.alertCard.color = alertCard
    if m.alertEyebrow <> invalid then m.alertEyebrow.color = accent
    if m.alertMeta <> invalid then m.alertMeta.color = muted
end sub

function fieldStr(obj as object, key as string) as string
    if obj = invalid then return ""
    if not obj.DoesExist(key) then return ""
    value = obj[key]
    if value = invalid then return ""
    return value.ToStr()
end function

function formatCountdown(p as object) as string
    if not p.DoesExist("countdown_seconds") or p.countdown_seconds = invalid
        return "--:--:--"
    end if
    secs = Int(p.countdown_seconds)
    sign = ""
    if secs < 0
        sign = "-"
        secs = Abs(secs)
    end if
    hours = Int(secs / 3600)
    minutes = Int((secs mod 3600) / 60)
    seconds = secs mod 60
    return sign + pad2(hours) + ":" + pad2(minutes) + ":" + pad2(seconds)
end function

function formatResult(p as object) as string
    place = fieldStr(p, "finish_place")
    finish = fieldStr(p, "finish_time")
    category = fieldStr(p, "result_category")
    if place = "" and finish = ""
        return ""
    end if
    parts = []
    if place <> ""
        parts.Push(pad2(Val(place)))
    end if
    if finish <> ""
        ' Strip fractional seconds for TV readability when present.
        dot = Instr(1, finish, ".")
        if dot > 0
            finish = Left(finish, dot - 1)
        end if
        parts.Push(finish)
    end if
    if category <> ""
        parts.Push(category)
    end if
    out = ""
    for i = 0 to parts.Count() - 1
        if i > 0 then out = out + " · "
        out = out + parts[i]
    end for
    return out
end function

function formatStartTime(raw as string) as string
    ' Accept "HH:MM:SS" or "HH:MM" and show 12-hour time.
    if raw = invalid or raw = "" then return ""
    if Len(raw) < 4 then return raw
    hour = Val(Left(raw, 2))
    minute = 0
    colon = Instr(1, raw, ":")
    if colon > 0 and Len(raw) >= colon + 2
        minute = Val(Mid(raw, colon + 1, 2))
    end if
    ampm = "AM"
    if hour >= 12
        ampm = "PM"
    end if
    hour12 = hour mod 12
    if hour12 = 0 then hour12 = 12
    return hour12.ToStr() + ":" + pad2(minute) + " " + ampm
end function

function formatClock12(iso as string) as string
    ' 2026-08-30T13:24:18 -> 1:24:18 PM
    if Len(iso) < 19 then return iso
    tPos = Instr(1, iso, "T")
    if tPos = 0 then return iso
    hh = Val(Mid(iso, tPos + 1, 2))
    mm = Mid(iso, tPos + 4, 2)
    ss = Mid(iso, tPos + 7, 2)
    ampm = "AM"
    if hh >= 12 then ampm = "PM"
    hour12 = hh mod 12
    if hour12 = 0 then hour12 = 12
    return hour12.ToStr() + ":" + mm + ":" + ss + " " + ampm
end function

function formatPrettyDate(isoDate as string) as string
    ' Keep YYYY-MM-DD readable; BrightScript has limited locale date helpers.
    if Len(isoDate) < 10 then return isoDate
    year = Left(isoDate, 4)
    month = Mid(isoDate, 6, 2)
    day = Mid(isoDate, 9, 2)
    months = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]
    mi = Val(month)
    if mi < 1 or mi > 12 then return isoDate
    return months[mi - 1] + " " + Val(day).ToStr() + ", " + year
end function

function pad2(n as dynamic) as string
    value = Int(Val(n.ToStr()))
    if value < 10
        return "0" + value.ToStr()
    end if
    return value.ToStr()
end function
