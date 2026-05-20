import Foundation
import SwiftUI

enum NotchState: Equatable { case closed, open }

class AppStore: ObservableObject {
    @Published var notchState: NotchState = .closed
    let wsClient   = WebSocketClient()
    let discovery  = AgentDiscovery()
}
