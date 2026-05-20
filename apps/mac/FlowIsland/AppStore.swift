import Foundation
import SwiftUI

enum NotchState: Equatable { case closed, open }
enum PanelTab:   Equatable { case overview, runs, memory }

class AppStore: ObservableObject {
    @Published var notchState:     NotchState = .closed
    @Published var activeTab:      PanelTab   = .overview
    @Published var isHoveringPill: Bool        = false
    let wsClient   = WebSocketClient()
    let discovery  = AgentDiscovery()
}
