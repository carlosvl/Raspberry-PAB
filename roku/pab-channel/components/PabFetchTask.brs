sub init()
    m.top.functionName = "fetch"
end sub

sub fetch()
    url = m.top.url
    m.top.error = ""
    m.top.response = ""
    if url = invalid or url = ""
        m.top.error = "empty url"
        return
    end if

    xfer = CreateObject("roUrlTransfer")
    xfer.SetUrl(url)
    xfer.SetCertificatesFile("common:/certs/ca-bundle.crt")
    xfer.InitClientCertificates()
    xfer.RetainBodyOnError(true)
    xfer.SetRequest("GET")

    port = CreateObject("roMessagePort")
    xfer.SetMessagePort(port)
    if not xfer.AsyncGetToString()
        m.top.error = "async get failed"
        return
    end if

    msg = wait(8000, port)
    if msg = invalid
        m.top.error = "timeout"
        return
    end if
    if type(msg) <> "roUrlEvent"
        m.top.error = "bad event"
        return
    end if

    code = msg.GetResponseCode()
    body = msg.GetString()
    if code < 200 or code >= 300
        m.top.error = "HTTP " + code.ToStr()
        return
    end if
    m.top.response = body
end sub
