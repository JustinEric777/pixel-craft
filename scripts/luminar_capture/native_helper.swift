import AppKit
import ApplicationServices
import CoreGraphics
import Foundation
import IOKit

private let bundleIdentifier = "com.skylum.luminarneo"

private enum HelperError: Error, CustomStringConvertible {
    case message(String)

    var description: String {
        switch self {
        case .message(let text): return text
        }
    }
}

private func attribute(_ element: AXUIElement, _ name: CFString) -> AnyObject? {
    var value: CFTypeRef?
    guard AXUIElementCopyAttributeValue(element, name, &value) == .success else {
        return nil
    }
    return value
}

private func stringAttribute(_ element: AXUIElement, _ name: CFString) -> String? {
    attribute(element, name) as? String
}

private func boolAttribute(_ element: AXUIElement, _ name: CFString) -> Bool? {
    (attribute(element, name) as? NSNumber)?.boolValue
}

private func numberAttribute(_ element: AXUIElement, _ name: CFString) -> Double? {
    (attribute(element, name) as? NSNumber)?.doubleValue
}

private func pointAttribute(_ element: AXUIElement, _ name: CFString) -> [Int]? {
    guard let value = attribute(element, name), CFGetTypeID(value) == AXValueGetTypeID() else {
        return nil
    }
    let axValue = value as! AXValue
    if AXValueGetType(axValue) == .cgPoint {
        var point = CGPoint.zero
        guard AXValueGetValue(axValue, .cgPoint, &point) else { return nil }
        return [Int(point.x.rounded()), Int(point.y.rounded())]
    }
    if AXValueGetType(axValue) == .cgSize {
        var size = CGSize.zero
        guard AXValueGetValue(axValue, .cgSize, &size) else { return nil }
        return [Int(size.width.rounded()), Int(size.height.rounded())]
    }
    return nil
}

private func jsonValue(_ value: AnyObject?) -> Any {
    guard let value else { return NSNull() }
    if let text = value as? String { return text }
    if let number = value as? NSNumber { return number }
    return String(describing: value)
}

private func runningApplication() throws -> NSRunningApplication {
    let applications = runningApplications()
    guard let app = applications.first(where: { $0.isActive }) ?? applications.first else {
        throw HelperError.message("Luminar Neo process is not running")
    }
    return app
}

private func runningApplications() -> [NSRunningApplication] {
    NSWorkspace.shared.runningApplications.filter {
        $0.bundleIdentifier == bundleIdentifier
    }
}

private func applicationElement() throws -> (NSRunningApplication, AXUIElement) {
    guard AXIsProcessTrusted() else {
        throw HelperError.message("Accessibility permission is not granted")
    }
    let app = try runningApplication()
    return (app, AXUIElementCreateApplication(app.processIdentifier))
}

private func windows(_ app: AXUIElement) -> [AXUIElement] {
    attribute(app, kAXWindowsAttribute as CFString) as? [AXUIElement] ?? []
}

private func children(_ element: AXUIElement) -> [AXUIElement] {
    attribute(element, kAXChildrenAttribute as CFString) as? [AXUIElement] ?? []
}

private func elements(_ root: AXUIElement) -> [AXUIElement] {
    var queue = [root]
    var result: [AXUIElement] = []
    var cursor = 0
    while cursor < queue.count {
        let element = queue[cursor]
        cursor += 1
        result.append(element)
        queue.append(contentsOf: children(element))
    }
    return result
}

private func frontWindow(_ app: AXUIElement) throws -> AXUIElement {
    if let focused = attribute(app, kAXFocusedWindowAttribute as CFString) {
        return focused as! AXUIElement
    }
    let candidates = windows(app)
    guard let window = candidates.max(by: { left, right in
        let leftSize = pointAttribute(left, kAXSizeAttribute as CFString) ?? [0, 0]
        let rightSize = pointAttribute(right, kAXSizeAttribute as CFString) ?? [0, 0]
        return leftSize[0] * leftSize[1] < rightSize[0] * rightSize[1]
    }) else {
        throw HelperError.message("Luminar Neo has no accessibility window")
    }
    return window
}

private func matches(_ element: AXUIElement, locator: String) -> Bool {
    stringAttribute(element, kAXIdentifierAttribute as CFString) == locator
        || stringAttribute(element, kAXTitleAttribute as CFString) == locator
        || stringAttribute(element, kAXDescriptionAttribute as CFString) == locator
        || stringAttribute(element, kAXHelpAttribute as CFString) == locator
        || stringAttribute(element, kAXValueAttribute as CFString) == locator
}

private func supportsPress(_ element: AXUIElement) -> Bool {
    var names: CFArray?
    guard AXUIElementCopyActionNames(element, &names) == .success,
          let actions = names as? [String] else { return false }
    return actions.contains(kAXPressAction as String)
}

private func targetScore(_ element: AXUIElement) -> Int {
    var score = 0
    if boolAttribute(element, kAXEnabledAttribute as CFString) != false { score += 8 }
    if supportsPress(element) { score += 4 }
    if attribute(element, kAXValueAttribute as CFString) != nil { score += 2 }
    if let size = pointAttribute(element, kAXSizeAttribute as CFString),
       size[0] > 0, size[1] > 0 {
        score += 1
    }
    return score
}

private func findElement(_ app: AXUIElement, locator: String) throws -> AXUIElement {
    let root = try frontWindow(app)
    var queue = [root]
    var cursor = 0
    var best: (element: AXUIElement, score: Int)?
    while cursor < queue.count {
        let element = queue[cursor]
        cursor += 1
        if matches(element, locator: locator) {
            let score = targetScore(element)
            if best == nil || score > best!.score {
                best = (element, score)
            }
        }
        queue.append(contentsOf: children(element))
    }
    guard let best else {
        throw HelperError.message("locator \(locator) matched no accessibility element")
    }
    return best.element
}

private func findFirstEnabledElement(_ app: AXUIElement, locator: String) throws -> AXUIElement {
    let root = try frontWindow(app)
    var queue = [root]
    var cursor = 0
    while cursor < queue.count {
        let element = queue[cursor]
        cursor += 1
        if matches(element, locator: locator),
           boolAttribute(element, kAXEnabledAttribute as CFString) != false {
            return element
        }
        queue.append(contentsOf: children(element))
    }
    throw HelperError.message("locator \(locator) matched no enabled accessibility element")
}

private func clickCenter(_ element: AXUIElement) throws {
    guard let position = pointAttribute(element, kAXPositionAttribute as CFString),
          let size = pointAttribute(element, kAXSizeAttribute as CFString) else {
        throw HelperError.message("accessibility element has no clickable bounds")
    }
    let point = CGPoint(
        x: CGFloat(position[0]) + CGFloat(size[0]) / 2.0,
        y: CGFloat(position[1]) + CGFloat(size[1]) / 2.0
    )
    guard let down = CGEvent(mouseEventSource: nil, mouseType: .leftMouseDown, mouseCursorPosition: point, mouseButton: .left),
          let up = CGEvent(mouseEventSource: nil, mouseType: .leftMouseUp, mouseCursorPosition: point, mouseButton: .left) else {
        throw HelperError.message("cannot create native mouse event")
    }
    down.post(tap: .cghidEventTap)
    usleep(30_000)
    up.post(tap: .cghidEventTap)
}

private func targetClickCenter(_ element: AXUIElement) throws {
    guard let position = pointAttribute(element, kAXPositionAttribute as CFString),
          let size = pointAttribute(element, kAXSizeAttribute as CFString) else {
        throw HelperError.message("accessibility element has no clickable bounds")
    }
    var pid: pid_t = 0
    guard AXUIElementGetPid(element, &pid) == .success, pid > 0 else {
        throw HelperError.message("accessibility element has no target process")
    }
    try clickPoint(
        CGPoint(
            x: CGFloat(position[0]) + CGFloat(size[0]) / 2.0,
            y: CGFloat(position[1]) + CGFloat(size[1]) / 2.0
        ),
        to: pid
    )
}

private func clickPoint(_ point: CGPoint, flags: CGEventFlags = []) throws {
    guard let move = CGEvent(mouseEventSource: nil, mouseType: .mouseMoved, mouseCursorPosition: point, mouseButton: .left),
          let down = CGEvent(mouseEventSource: nil, mouseType: .leftMouseDown, mouseCursorPosition: point, mouseButton: .left),
          let up = CGEvent(mouseEventSource: nil, mouseType: .leftMouseUp, mouseCursorPosition: point, mouseButton: .left) else {
        throw HelperError.message("cannot create native mouse event")
    }
    down.flags = flags
    up.flags = flags
    move.post(tap: .cghidEventTap)
    usleep(15_000)
    down.post(tap: .cghidEventTap)
    usleep(30_000)
    up.post(tap: .cghidEventTap)
}

private func clickPoint(
    _ point: CGPoint,
    to pid: pid_t,
    flags: CGEventFlags = []
) throws {
    guard let move = CGEvent(
        mouseEventSource: nil,
        mouseType: .mouseMoved,
        mouseCursorPosition: point,
        mouseButton: .left
    ), let down = CGEvent(
        mouseEventSource: nil,
        mouseType: .leftMouseDown,
        mouseCursorPosition: point,
        mouseButton: .left
    ), let up = CGEvent(
        mouseEventSource: nil,
        mouseType: .leftMouseUp,
        mouseCursorPosition: point,
        mouseButton: .left
    ) else {
        throw HelperError.message("cannot create targeted mouse event")
    }
    down.flags = flags
    up.flags = flags
    move.postToPid(pid)
    usleep(15_000)
    down.postToPid(pid)
    usleep(80_000)
    up.postToPid(pid)
}

private func rightClickPoint(_ point: CGPoint) throws {
    guard let down = CGEvent(
        mouseEventSource: nil,
        mouseType: .rightMouseDown,
        mouseCursorPosition: point,
        mouseButton: .right
    ), let up = CGEvent(
        mouseEventSource: nil,
        mouseType: .rightMouseUp,
        mouseCursorPosition: point,
        mouseButton: .right
    ) else {
        throw HelperError.message("cannot create right-click events")
    }
    down.post(tap: .cghidEventTap)
    usleep(80_000)
    up.post(tap: .cghidEventTap)
}

private func postMouseEvent(_ type: CGEventType, at point: CGPoint) throws {
    guard let event = CGEvent(
        mouseEventSource: nil,
        mouseType: type,
        mouseCursorPosition: point,
        mouseButton: .left
    ) else {
        throw HelperError.message("cannot create native mouse event")
    }
    event.post(tap: .cghidEventTap)
}

private func eventFlags(_ raw: String) throws -> CGEventFlags {
    var flags: CGEventFlags = []
    for modifier in raw.split(separator: ",").map(String.init).filter({ !$0.isEmpty }) {
        switch modifier {
        case "command": flags.insert(.maskCommand)
        case "shift": flags.insert(.maskShift)
        case "option": flags.insert(.maskAlternate)
        case "control": flags.insert(.maskControl)
        default: throw HelperError.message("unsupported key modifier: \(modifier)")
        }
    }
    return flags
}

private func postKeyEvent(keyCode: CGKeyCode, keyDown: Bool, flags: CGEventFlags) throws {
    guard let event = CGEvent(
        keyboardEventSource: nil,
        virtualKey: keyCode,
        keyDown: keyDown
    ) else {
        throw HelperError.message("cannot create native keyboard event")
    }
    event.flags = flags
    event.post(tap: .cghidEventTap)
}

private func dragPoint(from start: CGPoint, to end: CGPoint) throws {
    guard let move = CGEvent(
        mouseEventSource: nil,
        mouseType: .mouseMoved,
        mouseCursorPosition: start,
        mouseButton: .left
    ), let down = CGEvent(
        mouseEventSource: nil,
        mouseType: .leftMouseDown,
        mouseCursorPosition: start,
        mouseButton: .left
    ) else {
        throw HelperError.message("cannot create native drag event")
    }
    move.post(tap: .cghidEventTap)
    down.post(tap: .cghidEventTap)
    let steps = 12
    for step in 1...steps {
        let progress = CGFloat(step) / CGFloat(steps)
        let point = CGPoint(
            x: start.x + (end.x - start.x) * progress,
            y: start.y + (end.y - start.y) * progress
        )
        guard let drag = CGEvent(
            mouseEventSource: nil,
            mouseType: .leftMouseDragged,
            mouseCursorPosition: point,
            mouseButton: .left
        ) else {
            throw HelperError.message("cannot create native drag event")
        }
        drag.post(tap: .cghidEventTap)
        usleep(15_000)
    }
    guard let up = CGEvent(
        mouseEventSource: nil,
        mouseType: .leftMouseUp,
        mouseCursorPosition: end,
        mouseButton: .left
    ) else {
        throw HelperError.message("cannot create native drag event")
    }
    up.post(tap: .cghidEventTap)
}

private func dragPoint(from start: CGPoint, to end: CGPoint, to pid: pid_t) throws {
    guard let move = CGEvent(
        mouseEventSource: nil,
        mouseType: .mouseMoved,
        mouseCursorPosition: start,
        mouseButton: .left
    ), let down = CGEvent(
        mouseEventSource: nil,
        mouseType: .leftMouseDown,
        mouseCursorPosition: start,
        mouseButton: .left
    ) else {
        throw HelperError.message("cannot create targeted drag event")
    }
    // Metal-backed canvases such as Luminar's preview establish their brush
    // target from the preceding mouse-move event.  Posting a down event at a
    // new coordinate without that move is accepted by AppKit but ignored by
    // the canvas, yielding a no-op stroke and a disabled restore action.
    move.postToPid(pid)
    usleep(15_000)
    down.postToPid(pid)
    usleep(15_000)
    let steps = 12
    for step in 1...steps {
        let progress = CGFloat(step) / CGFloat(steps)
        let point = CGPoint(
            x: start.x + (end.x - start.x) * progress,
            y: start.y + (end.y - start.y) * progress
        )
        guard let drag = CGEvent(
            mouseEventSource: nil,
            mouseType: .leftMouseDragged,
            mouseCursorPosition: point,
            mouseButton: .left
        ) else {
            throw HelperError.message("cannot create targeted drag event")
        }
        drag.postToPid(pid)
        usleep(15_000)
    }
    guard let up = CGEvent(
        mouseEventSource: nil,
        mouseType: .leftMouseUp,
        mouseCursorPosition: end,
        mouseButton: .left
    ) else {
        throw HelperError.message("cannot create targeted drag event")
    }
    up.postToPid(pid)
}

private func isOnActiveDisplay(_ element: AXUIElement) -> Bool {
    guard let position = pointAttribute(element, kAXPositionAttribute as CFString),
          let size = pointAttribute(element, kAXSizeAttribute as CFString),
          size[0] > 0, size[1] > 0 else {
        return false
    }
    let point = CGPoint(
        x: CGFloat(position[0]) + CGFloat(size[0]) / 2.0,
        y: CGFloat(position[1]) + CGFloat(size[1]) / 2.0
    )
    var count: UInt32 = 0
    guard CGGetActiveDisplayList(0, nil, &count) == .success else { return false }
    var displays = [CGDirectDisplayID](repeating: 0, count: Int(count))
    guard CGGetActiveDisplayList(count, &displays, &count) == .success else { return false }
    return displays.prefix(Int(count)).contains { CGDisplayBounds($0).contains(point) }
}

@discardableResult
private func press(_ element: AXUIElement) throws -> String {
    if supportsPress(element), AXUIElementPerformAction(element, kAXPressAction as CFString) == .success {
        return "accessibility"
    }
    if [
        "MPCatalogFilterNodeViewNodeLabel",
        "MPInstrumentInfoViewControllerFileName",
    ].contains(stringAttribute(element, kAXIdentifierAttribute as CFString) ?? "") {
        try clickCenter(element)
        return "global-pointer"
    }
    try targetClickCenter(element)
    return "targeted-process"
}

private func hidIdleSeconds() throws -> Double {
    let service = IOServiceGetMatchingService(
        kIOMainPortDefault,
        IOServiceMatching("IOHIDSystem")
    )
    guard service != 0 else {
        throw HelperError.message("IOHIDSystem service is unavailable")
    }
    defer { IOObjectRelease(service) }
    guard let raw = IORegistryEntryCreateCFProperty(
        service,
        "HIDIdleTime" as CFString,
        kCFAllocatorDefault,
        0
    )?.takeRetainedValue() as? NSNumber else {
        throw HelperError.message("IOHIDSystem HIDIdleTime is unavailable")
    }
    return raw.doubleValue / 1_000_000_000.0
}

private func scroll(at point: CGPoint, lines: Int32) throws {
    guard let move = CGEvent(mouseEventSource: nil, mouseType: .mouseMoved, mouseCursorPosition: point, mouseButton: .left),
          let event = CGEvent(scrollWheelEvent2Source: nil, units: .line, wheelCount: 1, wheel1: lines, wheel2: 0, wheel3: 0) else {
        throw HelperError.message("cannot create native scroll event")
    }
    move.post(tap: .cghidEventTap)
    event.post(tap: .cghidEventTap)
}

private func triggerShortcut(keyCode: CGKeyCode, flags: CGEventFlags) throws {
    guard let down = CGEvent(keyboardEventSource: nil, virtualKey: keyCode, keyDown: true),
          let up = CGEvent(keyboardEventSource: nil, virtualKey: keyCode, keyDown: false) else {
        throw HelperError.message("cannot create native keyboard event")
    }
    down.flags = flags
    up.flags = flags
    down.post(tap: .cghidEventTap)
    usleep(30_000)
    up.post(tap: .cghidEventTap)
}

private func triggerShortcut(
    keyCode: CGKeyCode,
    flags: CGEventFlags,
    to pid: pid_t
) throws {
    guard let down = CGEvent(keyboardEventSource: nil, virtualKey: keyCode, keyDown: true),
          let up = CGEvent(keyboardEventSource: nil, virtualKey: keyCode, keyDown: false) else {
        throw HelperError.message("cannot create targeted keyboard event")
    }
    down.flags = flags
    up.flags = flags
    down.postToPid(pid)
    usleep(60_000)
    up.postToPid(pid)
}

private func describe(_ element: AXUIElement, index: Int) -> [String: Any] {
    let role = stringAttribute(element, kAXRoleAttribute as CFString)
    var payload: [String: Any] = [
        "index": index,
        "role": role ?? NSNull(),
        "subrole": stringAttribute(element, kAXSubroleAttribute as CFString) ?? NSNull(),
        "identifier": stringAttribute(element, kAXIdentifierAttribute as CFString) ?? NSNull(),
        "title": stringAttribute(element, kAXTitleAttribute as CFString) ?? NSNull(),
        "description": stringAttribute(element, kAXDescriptionAttribute as CFString) ?? NSNull(),
        "help": stringAttribute(element, kAXHelpAttribute as CFString) ?? NSNull(),
        "value": jsonValue(attribute(element, kAXValueAttribute as CFString)),
        "min_value": numberAttribute(element, kAXMinValueAttribute as CFString) ?? NSNull(),
        "max_value": numberAttribute(element, kAXMaxValueAttribute as CFString) ?? NSNull(),
        "enabled": boolAttribute(element, kAXEnabledAttribute as CFString) ?? NSNull(),
        "focused": boolAttribute(element, kAXFocusedAttribute as CFString) ?? NSNull(),
        "selected": boolAttribute(element, kAXSelectedAttribute as CFString) ?? NSNull(),
        "position": pointAttribute(element, kAXPositionAttribute as CFString) ?? NSNull(),
        "size": pointAttribute(element, kAXSizeAttribute as CFString) ?? NSNull(),
        "orientation": stringAttribute(element, kAXOrientationAttribute as CFString) ?? NSNull(),
    ]
    if role != kAXSliderRole as String && role != kAXScrollBarRole as String {
        payload["min_value"] = NSNull()
        payload["max_value"] = NSNull()
        payload["orientation"] = NSNull()
    }
    return payload
}

private let snapshotRoles: Set<String> = [
    kAXWindowRole as String,
    kAXButtonRole as String,
    kAXRadioButtonRole as String,
    kAXSliderRole as String,
    kAXScrollBarRole as String,
    kAXCheckBoxRole as String,
    kAXPopUpButtonRole as String,
    kAXTextFieldRole as String,
    kAXStaticTextRole as String,
    kAXImageRole as String,
    kAXMenuRole as String,
    kAXMenuItemRole as String,
    kAXSheetRole as String,
]

private func bestWindowInfo(pid: pid_t) -> [String: Any]? {
    guard let entries = CGWindowListCopyWindowInfo([.optionOnScreenOnly, .excludeDesktopElements], kCGNullWindowID) as? [[String: Any]] else {
        return nil
    }
    let candidates = entries.filter {
        ($0[kCGWindowOwnerPID as String] as? NSNumber)?.int32Value == pid
            && ($0[kCGWindowLayer as String] as? NSNumber)?.intValue == 0
    }
    guard let best = candidates.max(by: {
        let left = CGRect(dictionaryRepresentation: $0[kCGWindowBounds as String] as! CFDictionary) ?? .zero
        let right = CGRect(dictionaryRepresentation: $1[kCGWindowBounds as String] as! CFDictionary) ?? .zero
        return left.width * left.height < right.width * right.height
    }) else { return nil }
    let id = (best[kCGWindowNumber as String] as? NSNumber)?.uint32Value
    let bounds = (best[kCGWindowBounds as String] as? NSDictionary).flatMap {
        CGRect(dictionaryRepresentation: $0)
    }
    return [
        "window_id": id ?? 0,
        "bounds": bounds.map { [Int($0.origin.x), Int($0.origin.y), Int($0.width), Int($0.height)] } ?? NSNull(),
    ]
}

private func setValue(_ element: AXUIElement, raw: String) throws -> Any {
    let current = attribute(element, kAXValueAttribute as CFString)
    let value: AnyObject
    if current is NSNumber {
        guard let number = Double(raw) else {
            throw HelperError.message("invalid numeric AXValue: \(raw)")
        }
        value = NSNumber(value: number)
    } else {
        value = raw as NSString
    }
    let error = AXUIElementSetAttributeValue(element, kAXValueAttribute as CFString, value)
    guard error == .success else {
        throw HelperError.message("cannot set AXValue: \(error.rawValue)")
    }
    return jsonValue(attribute(element, kAXValueAttribute as CFString))
}

private func success(_ payload: [String: Any] = [:]) -> [String: Any] {
    var result = payload
    result["ok"] = true
    return result
}

private func snapshotPayload(_ root: AXUIElement) -> [[String: Any]] {
    elements(root).enumerated().compactMap { index, element -> [String: Any]? in
        guard let role = stringAttribute(element, kAXRoleAttribute as CFString),
              snapshotRoles.contains(role) else {
            return nil
        }
        return describe(element, index: index)
    }
}

private func execute(arguments: [String]) throws -> [String: Any] {
    let action = arguments.first ?? "state"
    if action == "hid-idle" {
        return success(["seconds": try hidIdleSeconds()])
    }
    if action == "cursor-position" {
        let point = CGEvent(source: nil)?.location ?? .zero
        return success(["position": [point.x, point.y]])
    }
    if action == "process-descriptors" {
        guard AXIsProcessTrusted() else {
            throw HelperError.message("Accessibility permission is not granted")
        }
        let payload = runningApplications().map { running -> [String: Any] in
            let app = AXUIElementCreateApplication(running.processIdentifier)
            let appWindows = windows(app)
            return [
                "pid": running.processIdentifier,
                "active": running.isActive,
                "window_count": appWindows.count,
                "window_roles": appWindows.map {
                    stringAttribute($0, kAXRoleAttribute as CFString) ?? ""
                },
                "window_identifiers": appWindows.map {
                    stringAttribute($0, kAXIdentifierAttribute as CFString) ?? ""
                },
                "cg_window": bestWindowInfo(pid: running.processIdentifier) ?? NSNull(),
            ]
        }
        return success(["processes": payload])
    }
    let (running, app) = try applicationElement()
    if action == "state" {
        let appWindows = windows(app)
        let mainWindowCount = appWindows.filter {
            stringAttribute($0, kAXIdentifierAttribute as CFString)
                == "MPLuminarMainWindowIdentifier"
        }.count
        var payload: [String: Any] = [
            "frontmost": running.isActive,
            "window_count": appWindows.count,
            "main_window_count": mainWindowCount,
            "pid": running.processIdentifier,
        ]
        if let window = appWindows.first {
            payload["title"] = stringAttribute(window, kAXTitleAttribute as CFString) ?? ""
        }
        if let info = bestWindowInfo(pid: running.processIdentifier) {
            payload.merge(info) { _, new in new }
        }
        return success(payload)
    }
    if action == "window-descriptors" {
        let payload = windows(app).enumerated().map { index, window in
            [
                "index": index,
                "role": stringAttribute(window, kAXRoleAttribute as CFString) ?? NSNull(),
                "subrole": stringAttribute(window, kAXSubroleAttribute as CFString) ?? NSNull(),
                "identifier": stringAttribute(window, kAXIdentifierAttribute as CFString) ?? NSNull(),
                "title": stringAttribute(window, kAXTitleAttribute as CFString) ?? NSNull(),
                "position": pointAttribute(window, kAXPositionAttribute as CFString) ?? NSNull(),
                "size": pointAttribute(window, kAXSizeAttribute as CFString) ?? NSNull(),
                "focused": boolAttribute(window, kAXFocusedAttribute as CFString) ?? NSNull(),
                "full_screen": boolAttribute(window, "AXFullScreen" as CFString) ?? NSNull(),
            ] as [String: Any]
        }
        return success(["windows": payload])
    }
    if action == "activate" {
        let activated = running.activate(options: [.activateIgnoringOtherApps])
        _ = AXUIElementSetAttributeValue(
            app,
            kAXFrontmostAttribute as CFString,
            kCFBooleanTrue
        )
        return success(["activated": activated])
    }
    let protectedGlobalPressLocators = [
        "MPCatalogFilterNodeViewNodeLabel",
        "MPInstrumentInfoViewControllerFileName",
    ]
    let protectedGlobalPress = action == "press"
        && arguments.count >= 2
        && protectedGlobalPressLocators.contains(arguments[1])
    let backgroundSafeActions: Set<String> = [
        "snapshot",
        "inspect",
        "read-attribute",
        "read-value-first",
        "perform-action",
        "set-selected",
        "press",
        "press-first",
        "ax-press",
        "ax-press-at",
        "set-value",
        "set-value-first",
        "set-value-at",
        "reset-all-edits",
        "reset-all-edits-status",
        "select-menu-item",
        "target-click-at",
        "target-scroll-at",
        "target-drag-at",
        "target-command-click-at",
        "target-shortcut",
    ]
    if !running.isActive
        && (!backgroundSafeActions.contains(action) || protectedGlobalPress) {
        _ = running.activate(options: [.activateIgnoringOtherApps])
        _ = AXUIElementSetAttributeValue(
            app,
            kAXFrontmostAttribute as CFString,
            kCFBooleanTrue
        )
        usleep(150_000)
    }
    if action == "reset-all-edits" || action == "reset-all-edits-status" {
        let actionsButton = try findElement(
            app,
            locator: "MPPhotoActionMoreActionsViewControllerMoreActionsButton"
        )
        let inputMode = try press(actionsButton)
        var resetElement: AXUIElement?
        for _ in 0..<20 {
            let currentRoot = try frontWindow(app)
            resetElement = elements(currentRoot).first {
                matches($0, locator: "ResetAllEdits")
            }
            if resetElement != nil { break }
            usleep(50_000)
        }
        guard let resetElement else {
            throw HelperError.message(
                "Restore Original did not appear in the actions popover"
            )
        }
        let enabled = boolAttribute(
            resetElement,
            kAXEnabledAttribute as CFString
        ) ?? false
        var performed = false
        if action == "reset-all-edits" && enabled {
            guard supportsPress(resetElement) else {
                throw HelperError.message("Restore Original does not support AXPress")
            }
            guard AXUIElementPerformAction(
                resetElement,
                kAXPressAction as CFString
            ) == .success else {
                throw HelperError.message("Restore Original AXPress failed")
            }
            performed = true
        } else {
            try triggerShortcut(
                keyCode: 53,
                flags: [],
                to: running.processIdentifier
            )
        }
        return success([
            "enabled": enabled,
            "performed": performed,
            "input_mode": inputMode,
        ])
    }
    if action == "select-menu-item" {
        guard arguments.count >= 3 else {
            throw HelperError.message(
                "select-menu-item requires a parent locator and item locator"
            )
        }
        let parentLocator = arguments[1]
        let itemLocator = arguments[2]
        let parent = try findElement(app, locator: parentLocator)
        let openMode = try press(parent)
        var item: AXUIElement?
        for _ in 0..<20 {
            item = elements(AXUIElementCreateSystemWide()).first {
                matches($0, locator: itemLocator) && isOnActiveDisplay($0)
            }
            if item != nil { break }
            usleep(50_000)
        }
        let selectMode: String
        if let item {
            selectMode = try press(item)
        } else {
            // NSPopUpButton menus are visible to the macOS UI server but are
            // not always attached to the app's AX tree.  In the current native
            // crop menu the requested Free item is the first row, immediately
            // above the selected Original row.  Use the measured popup
            // geometry and immediately restore the user's cursor.
            guard let position = pointAttribute(
                parent, kAXPositionAttribute as CFString
            ), let size = pointAttribute(parent, kAXSizeAttribute as CFString) else {
                throw HelperError.message(
                    "menu parent \(parentLocator) has no fallback geometry"
                )
            }
            let cursor = CGEvent(source: nil)?.location ?? .zero
            try clickPoint(CGPoint(
                x: CGFloat(position[0]) + CGFloat(size[0]) / 2.0,
                y: CGFloat(position[1]) - CGFloat(size[1]) * 0.875
            ))
            usleep(100_000)
            CGWarpMouseCursorPosition(cursor)
            selectMode = "guarded-global-popup-first-item"
        }
        usleep(100_000)
        return success([
            "parent": parentLocator,
            "item": itemLocator,
            "input_mode": "\(openMode)+\(selectMode)",
        ])
    }
    if action == "new-export" {
        let exportButton = try findElement(app, locator: "NSButton.Export")
        guard let position = pointAttribute(
            exportButton, kAXPositionAttribute as CFString
        ), let size = pointAttribute(exportButton, kAXSizeAttribute as CFString) else {
            throw HelperError.message("export button has no menu anchor geometry")
        }
        let cursor = CGEvent(source: nil)?.location ?? .zero
        let start = CGPoint(
            x: CGFloat(position[0]) + CGFloat(size[0]) / 2.0,
            y: CGFloat(position[1]) + CGFloat(size[1]) / 2.0
        )
        // Luminar right-aligns its export menu to the Export button.  The
        // first enabled row (New Export) is 52 points below the button and its
        // 171-point menu is centered 86 points left of the shared right edge.
        let clickX = Double(position[0] + size[0]) - 86.0
        let clickY = Double(position[1] + size[1]) + 52.0
        let end = CGPoint(x: CGFloat(clickX), y: CGFloat(clickY))
        try clickPoint(start)
        usleep(1_500_000)
        try clickPoint(end)
        usleep(150_000)
        CGWarpMouseCursorPosition(cursor)
        return success([
            "menu_item": "NSMenuItem.NewExport",
            "selection_mode": "guarded-global-popup-two-click",
            "input_mode": "guarded-global-popup",
            "anchor_position": position,
            "anchor_size": size,
            "click_position": [clickX, clickY],
        ])
    }
    if action == "go-to-folder" {
        try triggerShortcut(keyCode: 5, flags: [.maskCommand, .maskShift])
        return success(["shortcut": "command-shift-g"])
    }
    if action == "confirm" {
        try triggerShortcut(keyCode: 36, flags: [])
        return success(["key": "return"])
    }
    if action == "cancel" {
        try triggerShortcut(keyCode: 53, flags: [])
        return success(["key": "escape"])
    }
    let root = try frontWindow(app)
    if action == "snapshot" {
        return success(["nodes": snapshotPayload(root)])
    }
    if action == "inspect" {
        guard arguments.count >= 2 else {
            throw HelperError.message("inspect requires a locator")
        }
        let element = try findElement(app, locator: arguments[1])
        var actionNames: CFArray?
        var attributeNames: CFArray?
        _ = AXUIElementCopyActionNames(element, &actionNames)
        _ = AXUIElementCopyAttributeNames(element, &attributeNames)
        let attributes = attributeNames as? [String] ?? []
        var settable: [String] = []
        for name in attributes {
            var canSet: DarwinBoolean = false
            if AXUIElementIsAttributeSettable(element, name as CFString, &canSet) == .success,
               canSet.boolValue {
                settable.append(name)
            }
        }
        return success([
            "locator": arguments[1],
            "actions": actionNames as? [String] ?? [],
            "attributes": attributes,
            "settable_attributes": settable,
        ])
    }
    if action == "read-attribute" {
        guard arguments.count >= 3 else {
            throw HelperError.message("read-attribute requires a locator and attribute")
        }
        let element = try findElement(app, locator: arguments[1])
        return success([
            "locator": arguments[1],
            "attribute": arguments[2],
            "value": jsonValue(attribute(element, arguments[2] as CFString)),
        ])
    }
    if action == "perform-action" {
        guard arguments.count >= 3 else {
            throw HelperError.message("perform-action requires a locator and action")
        }
        let element = try findElement(app, locator: arguments[1])
        guard AXUIElementPerformAction(element, arguments[2] as CFString) == .success else {
            throw HelperError.message("accessibility action \(arguments[2]) failed for \(arguments[1])")
        }
        return success(["locator": arguments[1], "action": arguments[2]])
    }
    if action == "set-selected" {
        guard arguments.count >= 3 else {
            throw HelperError.message("set-selected requires a locator and boolean")
        }
        let element = try findElement(app, locator: arguments[1])
        let selected = ["true", "1", "yes"].contains(arguments[2].lowercased())
        guard AXUIElementSetAttributeValue(
            element,
            kAXSelectedAttribute as CFString,
            selected ? kCFBooleanTrue : kCFBooleanFalse
        ) == .success else {
            throw HelperError.message("AXSelected failed for \(arguments[1])")
        }
        return success(["locator": arguments[1], "selected": selected])
    }
    if action == "open-export-menu" {
        try press(findElement(app, locator: "NSButton.Export"))
        usleep(250_000)
        return success(["nodes": snapshotPayload(try frontWindow(app))])
    }
    if action == "scroll-at" {
        guard arguments.count >= 4,
              let x = Double(arguments[1]),
              let y = Double(arguments[2]),
              let lines = Int32(arguments[3]) else {
            throw HelperError.message("scroll-at requires x, y and lines")
        }
        try scroll(at: CGPoint(x: x, y: y), lines: lines)
        return success(["position": [x, y], "lines": lines])
    }
    if action == "click-at" {
        guard arguments.count >= 3,
              let x = Double(arguments[1]),
              let y = Double(arguments[2]) else {
            throw HelperError.message("click-at requires x and y")
        }
        try clickPoint(CGPoint(x: x, y: y))
        return success(["position": [x, y]])
    }
    if action == "restored-click-at" {
        guard arguments.count >= 3,
              let x = Double(arguments[1]),
              let y = Double(arguments[2]) else {
            throw HelperError.message("restored-click-at requires x and y")
        }
        let cursor = CGEvent(source: nil)?.location ?? .zero
        try clickPoint(CGPoint(x: x, y: y))
        CGWarpMouseCursorPosition(cursor)
        return success([
            "position": [x, y],
            "cursor_restored_to": [cursor.x, cursor.y],
            "input_mode": "guarded-global-canvas",
        ])
    }
    if action == "target-click-at" {
        guard arguments.count >= 3,
              let x = Double(arguments[1]),
              let y = Double(arguments[2]) else {
            throw HelperError.message("target-click-at requires x and y")
        }
        try clickPoint(CGPoint(x: x, y: y), to: running.processIdentifier)
        return success(["position": [x, y], "target_pid": running.processIdentifier])
    }
    if action == "target-scroll-at" {
        guard arguments.count >= 4,
              let x = Double(arguments[1]),
              let y = Double(arguments[2]),
              let lines = Int32(arguments[3]),
              let event = CGEvent(
                scrollWheelEvent2Source: nil,
                units: .line,
                wheelCount: 1,
                wheel1: lines,
                wheel2: 0,
                wheel3: 0
              ) else {
            throw HelperError.message("target-scroll-at requires x, y and lines")
        }
        event.location = CGPoint(x: x, y: y)
        event.postToPid(running.processIdentifier)
        return success([
            "position": [x, y],
            "lines": lines,
            "target_pid": running.processIdentifier,
        ])
    }
    if action == "right-click-at" {
        guard arguments.count >= 3,
              let x = Double(arguments[1]),
              let y = Double(arguments[2]) else {
            throw HelperError.message("right-click-at requires x and y")
        }
        try rightClickPoint(CGPoint(x: x, y: y))
        return success(["position": [x, y], "button": "right"])
    }
    if action == "mouse-down-at" || action == "mouse-up-at" {
        guard arguments.count >= 3,
              let x = Double(arguments[1]),
              let y = Double(arguments[2]) else {
            throw HelperError.message("\(action) requires x and y")
        }
        try postMouseEvent(
            action == "mouse-down-at" ? .leftMouseDown : .leftMouseUp,
            at: CGPoint(x: x, y: y)
        )
        return success(["position": [x, y], "action": action])
    }
    if action == "mouse-move-at" {
        guard arguments.count >= 3,
              let x = Double(arguments[1]),
              let y = Double(arguments[2]) else {
            throw HelperError.message("mouse-move-at requires x and y")
        }
        try postMouseEvent(.mouseMoved, at: CGPoint(x: x, y: y))
        return success(["position": [x, y], "action": action])
    }
    if action == "key-down" || action == "key-up" {
        guard arguments.count >= 2, let rawKeyCode = UInt16(arguments[1]) else {
            throw HelperError.message("\(action) requires a numeric key code")
        }
        let flags = try eventFlags(arguments.count >= 3 ? arguments[2] : "")
        try postKeyEvent(
            keyCode: CGKeyCode(rawKeyCode),
            keyDown: action == "key-down",
            flags: flags
        )
        return success(["key_code": rawKeyCode, "action": action])
    }
    if action == "shortcut" {
        guard arguments.count >= 2, let rawKeyCode = UInt16(arguments[1]) else {
            throw HelperError.message("shortcut requires a numeric key code")
        }
        let flags = try eventFlags(arguments.count >= 3 ? arguments[2] : "")
        try triggerShortcut(keyCode: CGKeyCode(rawKeyCode), flags: flags)
        return success(["key_code": rawKeyCode, "action": action])
    }
    if action == "target-shortcut" {
        guard arguments.count >= 2, let rawKeyCode = UInt16(arguments[1]) else {
            throw HelperError.message("target-shortcut requires a numeric key code")
        }
        let flags = try eventFlags(arguments.count >= 3 ? arguments[2] : "")
        try triggerShortcut(
            keyCode: CGKeyCode(rawKeyCode),
            flags: flags,
            to: running.processIdentifier
        )
        return success([
            "key_code": rawKeyCode,
            "action": action,
            "target_pid": running.processIdentifier,
        ])
    }
    if action == "drag-at" {
        guard arguments.count >= 5,
              let startX = Double(arguments[1]),
              let startY = Double(arguments[2]),
              let endX = Double(arguments[3]),
              let endY = Double(arguments[4]) else {
            throw HelperError.message("drag-at requires start x/y and end x/y")
        }
        try dragPoint(
            from: CGPoint(x: startX, y: startY),
            to: CGPoint(x: endX, y: endY)
        )
        return success(["start": [startX, startY], "end": [endX, endY]])
    }
    if action == "restored-drag-at" {
        guard arguments.count >= 5,
              let startX = Double(arguments[1]),
              let startY = Double(arguments[2]),
              let endX = Double(arguments[3]),
              let endY = Double(arguments[4]) else {
            throw HelperError.message("restored-drag-at requires start x/y and end x/y")
        }
        let cursor = CGEvent(source: nil)?.location ?? .zero
        try dragPoint(
            from: CGPoint(x: startX, y: startY),
            to: CGPoint(x: endX, y: endY)
        )
        CGWarpMouseCursorPosition(cursor)
        return success([
            "start": [startX, startY],
            "end": [endX, endY],
            "cursor_restored_to": [cursor.x, cursor.y],
            "input_mode": "guarded-global-canvas",
        ])
    }
    if action == "target-drag-at" {
        guard arguments.count >= 5,
              let startX = Double(arguments[1]),
              let startY = Double(arguments[2]),
              let endX = Double(arguments[3]),
              let endY = Double(arguments[4]) else {
            throw HelperError.message("target-drag-at requires start x/y and end x/y")
        }
        try dragPoint(
            from: CGPoint(x: startX, y: startY),
            to: CGPoint(x: endX, y: endY),
            to: running.processIdentifier
        )
        return success([
            "start": [startX, startY],
            "end": [endX, endY],
            "target_pid": running.processIdentifier,
        ])
    }
    if action == "command-click-at" {
        guard arguments.count >= 3,
              let x = Double(arguments[1]),
              let y = Double(arguments[2]) else {
            throw HelperError.message("command-click-at requires x and y")
        }
        try clickPoint(CGPoint(x: x, y: y), flags: [.maskCommand])
        return success(["position": [x, y], "modifier": "command"])
    }
    if action == "target-command-click-at" {
        guard arguments.count >= 3,
              let x = Double(arguments[1]),
              let y = Double(arguments[2]) else {
            throw HelperError.message("target-command-click-at requires x and y")
        }
        try clickPoint(
            CGPoint(x: x, y: y),
            to: running.processIdentifier,
            flags: [.maskCommand]
        )
        return success([
            "position": [x, y],
            "modifier": "command",
            "target_pid": running.processIdentifier,
        ])
    }
    guard arguments.count >= 2 else {
        throw HelperError.message("action \(action) requires a target")
    }
    if action == "press" {
        let inputMode = try press(findElement(app, locator: arguments[1]))
        return success(["locator": arguments[1], "input_mode": inputMode])
    }
    if action == "ax-press" {
        let element = try findElement(app, locator: arguments[1])
        guard supportsPress(element) else {
            throw HelperError.message("accessibility element does not support AXPress")
        }
        guard AXUIElementPerformAction(
            element, kAXPressAction as CFString
        ) == .success else {
            throw HelperError.message("AXPress failed for \(arguments[1])")
        }
        return success(["locator": arguments[1], "action": "AXPress"])
    }
    if action == "press-at" {
        guard let index = Int(arguments[1]) else { throw HelperError.message("invalid index") }
        let candidates = elements(root)
        guard candidates.indices.contains(index) else { throw HelperError.message("invalid index") }
        let inputMode = try press(candidates[index])
        return success(["index": index, "input_mode": inputMode])
    }
    if action == "ax-press-at" {
        guard let index = Int(arguments[1]) else {
            throw HelperError.message("invalid index")
        }
        let candidates = elements(root)
        guard candidates.indices.contains(index) else {
            throw HelperError.message("invalid index")
        }
        let element = candidates[index]
        guard supportsPress(element) else {
            throw HelperError.message("accessibility element does not support AXPress")
        }
        guard AXUIElementPerformAction(
            element, kAXPressAction as CFString
        ) == .success else {
            throw HelperError.message("AXPress failed for index \(index)")
        }
        return success(["index": index, "action": "AXPress"])
    }
    if action == "set-value" {
        guard arguments.count >= 3 else { throw HelperError.message("set-value requires a value") }
        let value = try setValue(findElement(app, locator: arguments[1]), raw: arguments[2])
        return success(["locator": arguments[1], "value": value])
    }
    if action == "read-value-first" {
        let element = try findFirstEnabledElement(app, locator: arguments[1])
        return success([
            "locator": arguments[1],
            "value": jsonValue(attribute(element, kAXValueAttribute as CFString)),
        ])
    }
    if action == "set-value-first" {
        guard arguments.count >= 3 else {
            throw HelperError.message("set-value-first requires a value")
        }
        let element = try findFirstEnabledElement(app, locator: arguments[1])
        let value = try setValue(element, raw: arguments[2])
        return success(["locator": arguments[1], "value": value])
    }
    if action == "press-first" {
        let inputMode = try press(findFirstEnabledElement(app, locator: arguments[1]))
        return success(["locator": arguments[1], "input_mode": inputMode])
    }
    if action == "set-value-at" {
        guard arguments.count >= 3, let index = Int(arguments[1]) else {
            throw HelperError.message("set-value-at requires index and value")
        }
        let candidates = elements(root)
        guard candidates.indices.contains(index) else { throw HelperError.message("invalid index") }
        return success(["index": index, "value": try setValue(candidates[index], raw: arguments[2])])
    }
    throw HelperError.message("unsupported action: \(action)")
}

do {
    let payload = try execute(arguments: Array(CommandLine.arguments.dropFirst()))
    let data = try JSONSerialization.data(withJSONObject: payload, options: [])
    print(String(decoding: data, as: UTF8.self))
} catch {
    let payload: [String: Any] = ["ok": false, "error": String(describing: error)]
    let data = try JSONSerialization.data(withJSONObject: payload, options: [])
    FileHandle.standardError.write(data)
    FileHandle.standardError.write(Data("\n".utf8))
    exit(1)
}
