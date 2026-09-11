sub init()
    m.top.functionName = "fetch"
end sub

sub fetch()
    url = m.top.url
    if url = invalid or url = ""
        m.top.error = "empty url"
        return
    end if

    xfer = CreateObject("roUrlTransfer")
    port = CreateObject("roMessagePort")
    xfer.SetMessagePort(port)
    xfer.SetUrl(url)
    xfer.RetainBodyOnError(true)
    ' Plain HTTP to the Pi — do not InitClientCertificates (breaks LAN GETs).
    if Left(LCase(url), 8) = "https://"
        xfer.SetCertificatesFile("common:/certs/ca-bundle.crt")
        xfer.InitClientCertificates()
    end if

    if not xfer.AsyncGetToString()
        m.top.error = "async get failed"
        return
    end if

    msg = wait(10000, port)
    if msg = invalid
        m.top.error = "timeout " + url
        return
    end if
    if type(msg) <> "roUrlEvent"
        m.top.error = "bad event"
        return
    end if

    code = msg.GetResponseCode()
    body = msg.GetString()
    if code < 200 or code >= 300
        failure = "HTTP " + code.ToStr()
        if body <> invalid and body <> ""
            failure = failure + " " + Left(body, 80)
        end if
        m.top.error = failure
        return
    end if
    if body = invalid or body = ""
        m.top.error = "empty body"
        return
    end if
    m.top.response = body
end sub
