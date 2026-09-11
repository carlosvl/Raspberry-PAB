sub init()
    m.titleLabel = m.top.findNode("titleLabel")
    m.clockLabel = m.top.findNode("clockLabel")
    m.dateLabel = m.top.findNode("dateLabel")
    m.rowsLabel = m.top.findNode("rowsLabel")
    m.statusLabel = m.top.findNode("statusLabel")
    m.alertOverlay = m.top.findNode("alertOverlay")
    m.alertMessage = m.top.findNode("alertMessage")
    m.alertMeta = m.top.findNode("alertMeta")

    m.baseUrl = ""
    m.pageOffset = 0
    m.pageSize = 14
    m.participants = []
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
    m.statusLabel.text = "Connecting to " + m.baseUrl + "…"
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
        err = "request failed"
    end if
    m.statusLabel.text = "Reconnect: " + err
    m.alertOverlay.visible = false
end sub

sub onBoardResponse()
    if m.fetchTask = invalid then return
    raw = m.fetchTask.response
    if raw = invalid or raw = ""
        onBoardError()
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
        m.clockLabel.text = formatClock(parsed.kiosk_now.ToStr())
    end if

    if parsed.DoesExist("display_date") and parsed.display_date <> invalid
        m.dateLabel.text = parsed.display_date.ToStr()
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
            if meta <> ""
                meta = meta + " · start " + alert.start_time.ToStr()
            else
                meta = "start " + alert.start_time.ToStr()
            end if
        end if
        m.alertMessage.text = msg
        m.alertMeta.text = meta
        m.alertOverlay.visible = (msg <> "")
    else
        m.alertOverlay.visible = false
    end if

    count = m.participants.Count()
    m.statusLabel.text = count.ToStr() + " riders · " + m.baseUrl
end sub

sub renderRows()
    if m.participants.Count() = 0
        m.rowsLabel.text = "No riders scheduled for today."
        return
    end if

    lines = []
    last = m.pageOffset + m.pageSize - 1
    if last >= m.participants.Count()
        last = m.participants.Count() - 1
    end if
    for i = m.pageOffset to last
        p = m.participants[i]
        name = fieldStr(p, "name")
        race = fieldStr(p, "race")
        callUp = fieldStr(p, "call_up")
        startTime = fieldStr(p, "start_time")
        countdown = formatCountdown(p)
        result = formatResult(p)
        line = padRight(name, 24) + " " + padRight(race, 16) + " " + padRight(callUp, 16) + " " + padRight(startTime, 10) + " " + padRight(countdown, 10) + " " + result
        lines.Push(line)
    end for

    if m.participants.Count() > m.pageSize
        page = Int(m.pageOffset / m.pageSize) + 1
        pages = Int((m.participants.Count() + m.pageSize - 1) / m.pageSize)
        lines.Push("")
        lines.Push("Page " + page.ToStr() + " / " + pages.ToStr())
    end if

    text = ""
    for i = 0 to lines.Count() - 1
        if i > 0
            text = text + chr(10)
        end if
        text = text + lines[i]
    end for
    m.rowsLabel.text = text
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
        return "--"
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
    if hours > 0
        return sign + hours.ToStr() + "h" + pad2(minutes)
    end if
    return sign + pad2(minutes) + ":" + pad2(seconds)
end function

function formatResult(p as object) as string
    place = fieldStr(p, "finish_place")
    finish = fieldStr(p, "finish_time")
    if place <> "" and finish <> ""
        return "#" + place + " " + finish
    end if
    if place <> ""
        return "#" + place
    end if
    if finish <> ""
        return finish
    end if
    return ""
end function

function formatClock(iso as string) as string
    ' Expect ISO-ish timestamps; show HH:MM:SS when possible.
    if Len(iso) >= 19
        ' 2026-09-11T14:30:00...
        tPos = Instr(1, iso, "T")
        if tPos > 0 and Len(iso) >= tPos + 8
            return Mid(iso, tPos + 1, 8)
        end if
    end if
    return iso
end function

function padRight(text as string, width as integer) as string
    if text = invalid then text = ""
    if Len(text) >= width
        return Left(text, width)
    end if
    out = text
    while Len(out) < width
        out = out + " "
    end while
    return out
end function

function pad2(n as integer) as string
    if n < 10
        return "0" + n.ToStr()
    end if
    return n.ToStr()
end function
