import AppKit
import SwiftUI

private let NOTCH_W: CGFloat  = 250
private let PANEL_W: CGFloat  = 420
private let PANEL_H: CGFloat  = 560
private let COLLAPSE_DELAY: TimeInterval = 0.35

class AppDelegate: NSObject, NSApplicationDelegate {

    var panel: NSPanel!
    private var hostingView: NSHostingView<ContentView>!
    private let store = AppStore()

    private var collapseTimer: Timer?
    private var mouseMonitor: Any?

    // MARK: - Launch

    func applicationDidFinishLaunching(_ notification: Notification) {
        NSApp.setActivationPolicy(.accessory)
        buildPanel()
        startMouseTracking()
        store.discovery.start(wsClient: store.wsClient)
    }

    // MARK: - Panel

    private func buildPanel() {
        guard let screen = NSScreen.main else { return }

        let notchH = notchHeight(screen)
        let notchX = (screen.frame.width - NOTCH_W) / 2

        panel = NSPanel(
            contentRect: NSRect(x: notchX, y: screen.frame.maxY - notchH, width: NOTCH_W, height: notchH),
            styleMask: [.borderless, .nonactivatingPanel],
            backing: .buffered,
            defer: false
        )
        panel.level              = NSWindow.Level(rawValue: NSWindow.Level.mainMenu.rawValue + 3)
        panel.backgroundColor    = .clear
        panel.isOpaque           = false
        panel.hasShadow          = false
        panel.ignoresMouseEvents = false
        panel.collectionBehavior = [.canJoinAllSpaces, .stationary, .ignoresCycle]
        panel.isMovable          = false

        let content = ContentView(store: store)
        hostingView = NSHostingView(rootView: content)
        hostingView.autoresizingMask = [.width, .height]
        panel.contentView = hostingView

        panel.orderFrontRegardless()
    }

    // MARK: - Expand / Collapse

    func expand() {
        collapseTimer?.invalidate()
        collapseTimer = nil
        guard let screen = NSScreen.main else { return }
        let notchH = notchHeight(screen)
        let totalH = notchH + PANEL_H
        let x = (screen.frame.width - PANEL_W) / 2
        let y = screen.frame.maxY - totalH
        panel.setFrame(NSRect(x: x, y: y, width: PANEL_W, height: totalH), display: true, animate: false)
        panel.hasShadow = true

        DispatchQueue.main.async { self.store.isExpanded = true }
    }

    func scheduleCollapse() {
        collapseTimer?.invalidate()
        collapseTimer = Timer.scheduledTimer(withTimeInterval: COLLAPSE_DELAY, repeats: false) { [weak self] _ in
            self?.collapse()
        }
    }

    func collapse() {
        collapseTimer?.invalidate()
        collapseTimer = nil
        guard let screen = NSScreen.main else { return }
        let notchH = notchHeight(screen)
        let x = (screen.frame.width - NOTCH_W) / 2
        let y = screen.frame.maxY - notchH
        panel.setFrame(NSRect(x: x, y: y, width: NOTCH_W, height: notchH), display: true, animate: false)
        panel.hasShadow = false

        DispatchQueue.main.async { self.store.isExpanded = false }
    }

    // MARK: - Mouse tracking

    private func startMouseTracking() {
        mouseMonitor = NSEvent.addGlobalMonitorForEvents(matching: [.mouseMoved]) { [weak self] _ in
            guard let self else { return }
            let loc = NSEvent.mouseLocation
            if self.notchZone.contains(loc) {
                self.collapseTimer?.invalidate()
                self.collapseTimer = nil
                if !self.store.isExpanded { self.expand() }
            } else if !self.panelZone.contains(loc) {
                if self.store.isExpanded { self.scheduleCollapse() }
            }
        }
    }

    private var notchZone: NSRect {
        guard let screen = NSScreen.main else { return .zero }
        let h = notchHeight(screen)
        return NSRect(x: (screen.frame.width - NOTCH_W) / 2, y: screen.frame.maxY - h, width: NOTCH_W, height: h)
    }

    private var panelZone: NSRect {
        guard let screen = NSScreen.main else { return .zero }
        let h = notchHeight(screen) + PANEL_H
        return NSRect(x: (screen.frame.width - PANEL_W) / 2, y: screen.frame.maxY - h, width: PANEL_W, height: h)
    }

    // MARK: - Helpers

    private func notchHeight(_ screen: NSScreen) -> CGFloat {
        let inset = screen.safeAreaInsets.top
        return inset > 0 ? inset : 37
    }
}
