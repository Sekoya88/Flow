import SwiftUI

@main
struct FlowIslandApp: App {
    @NSApplicationDelegateAdaptor(AppDelegate.self) var delegate

    var body: some Scene {
        // No windows — the NSPanel in AppDelegate is the entire UI.
        Settings { EmptyView() }
    }
}
