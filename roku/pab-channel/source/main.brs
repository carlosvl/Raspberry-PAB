sub Main(args as dynamic)
    screen = CreateObject("roSGScreen")
    port = CreateObject("roMessagePort")
    screen.setMessagePort(port)

    scene = screen.CreateScene("PabBoardScene")
    screen.show()

    baseUrl = ""
    if args <> invalid and type(args) = "roAssociativeArray"
        if args.DoesExist("contentId") and args.contentId <> invalid
            baseUrl = args.contentId.ToStr().Trim()
        else if args.DoesExist("contentID") and args.contentID <> invalid
            baseUrl = args.contentID.ToStr().Trim()
        end if
    end if

    if baseUrl = ""
        sec = CreateObject("roRegistrySection", "pab")
        saved = sec.Read("baseUrl")
        if saved <> invalid and saved <> ""
            baseUrl = saved
        else
            ' Last resort when opened from the home row with no deep link.
            baseUrl = "http://10.42.0.1:8080"
        end if
    end if

    scene.baseUrl = baseUrl

    while true
        msg = wait(0, port)
        msgType = type(msg)
        if msgType = "roSGScreenEvent"
            if msg.isScreenClosed() then return
        end if
    end while
end sub
