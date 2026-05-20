import Foundation
import SwiftUI

// Central observable state shared between AppDelegate and ContentView
class AppStore: ObservableObject {
    @Published var isExpanded: Bool = false
    let wsClient   = WebSocketClient()
    let discovery  = AgentDiscovery()
}
