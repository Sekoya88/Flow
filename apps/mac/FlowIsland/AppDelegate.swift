import AppKit
import SwiftUI
import Combine
import CoreGraphics

// Panel is always the full expanded size — never resized at runtime.
// Only SwiftUI content inside morphs via spring animation.
private let PILL_W:          CGFloat = 200
private let PANEL_W:         CGFloat = 540
private let PANEL_CONTENT_H: CGFloat = 500
private let SHADOW_PAD:      CGFloat = 20

class AppDelegate: NSObject, NSApplicationDelegate {

    var panel: NSPanel!
    private var hostingView: NSHostingView<ContentView>!
    let store = AppStore()

    private var mouseMonitor: Any?
    private var cancellables  = Set<AnyCancellable>()

    // MARK: - Launch

    func applicationDidFinishLaunching(_ notification: Notification) {
        NSApp.setActivationPolicy(.accessory)
        buildPanel()
        observeNotchState()
        startMouseTracking()
        store.discovery.start(wsClient: store.wsClient)
    }

    // MARK: - Screen selection

    /// Returns the MacBook's built-in LCD panel.
    /// CGDisplayIsBuiltin is the only reliable identifier — it's hardware-level and unaffected
    /// by which screen is "main", which has the menubar, or multimonitor arrangement.
    private func notchScreen() -> NSScreen? {
        NSScreen.screens.first(where: { screen in
            let id = screen.deviceDescription[NSDeviceDescriptionKey("NSScreenNumber")] as? CGDirectDisplayID ?? 0
            return CGDisplayIsBuiltin(id) != 0
        }) ?? NSScreen.screens.first(where: { $0.safeAreaInsets.top > 0 }) ?? NSScreen.screens.first
    }

    // MARK: - Panel (fixed size, never changes)

    private func buildPanel() {
        guard let screen = notchScreen() else { return }
        let notchH = notchHeight(screen)
        let totalH = notchH + PANEL_CONTENT_H + SHADOW_PAD
        let x = screen.frame.minX + (screen.frame.width - PANEL_W) / 2
        let y = screen.frame.maxY - totalH

        panel = NSPanel(
            contentRect: NSRect(x: x, y: y, width: PANEL_W, height: totalH),
            styleMask:   [.borderless, .nonactivatingPanel],
            backing:     .buffered,
            defer:       false
        )
        panel.level              = NSWindow.Level(rawValue: NSWindow.Level.mainMenu.rawValue + 3)
        panel.backgroundColor    = .clear
        panel.isOpaque           = false
        panel.hasShadow          = false
        panel.ignoresMouseEvents = true   // starts closed; mouse events re-enabled on open
        panel.collectionBehavior = [.canJoinAllSpaces, .stationary, .ignoresCycle]
        panel.isMovable          = false

        hostingView = NSHostingView(rootView: ContentView(store: store))
        hostingView.autoresizingMask = [.width, .height]
        panel.contentView = hostingView
        panel.orderFrontRegardless()
    }

    // MARK: - Sync ignoresMouseEvents with notch state via Combine

    private func observeNotchState() {
        store.$notchState
            .receive(on: RunLoop.main)
            .sink { [weak self] state in
                self?.panel.ignoresMouseEvents = (state == .closed)
            }
            .store(in: &cancellables)
    }

    // MARK: - Global mouse monitor (open on pill entry, close on panel exit)

    private func startMouseTracking() {
        mouseMonitor = NSEvent.addGlobalMonitorForEvents(matching: [.mouseMoved]) { [weak self] _ in
            guard let self else { return }
            let loc   = NSEvent.mouseLocation
            let state = self.store.notchState
            guard let screen = self.notchScreen() else { return }

            if state == .closed && self.pillZone(screen).contains(loc) {
                // Cursor entered pill — open
                self.panel.ignoresMouseEvents = false
                DispatchQueue.main.async {
                    withAnimation(.spring(response: 0.42, dampingFraction: 0.8)) {
                        self.store.notchState = .open
                    }
                }
            } else if state == .open && !self.panelZone(screen).contains(loc) {
                // Cursor left panel — close
                DispatchQueue.main.async {
                    withAnimation(.spring(response: 0.45, dampingFraction: 1.0)) {
                        self.store.notchState = .closed
                    }
                }
            }
        }
    }

    // MARK: - Helpers

    private func notchHeight(_ screen: NSScreen) -> CGFloat {
        let inset = screen.safeAreaInsets.top
        return inset > 0 ? inset : 37
    }

    private func pillZone(_ screen: NSScreen) -> NSRect {
        let h = notchHeight(screen)
        return NSRect(
            x: screen.frame.minX + (screen.frame.width - PILL_W) / 2,
            y: screen.frame.maxY - h,
            width: PILL_W, height: h
        )
    }

    private func panelZone(_ screen: NSScreen) -> NSRect {
        let h   = notchHeight(screen)
        let buf: CGFloat = 16
        return NSRect(
            x: screen.frame.minX + (screen.frame.width - PANEL_W) / 2 - buf,
            y: screen.frame.maxY - (h + PANEL_CONTENT_H) - buf,
            width:  PANEL_W + buf * 2,
            height: h + PANEL_CONTENT_H + buf
        )
    }
}
