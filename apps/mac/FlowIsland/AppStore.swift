import Combine
import Foundation
import SwiftUI

enum NotchState: Equatable { case closed, open }
enum PanelTab:   Equatable { case overview, runs, memory }

struct AgentInfo: Identifiable, Equatable {
    let id: String
    let name: String
}

class AppStore: ObservableObject {
    @Published var notchState:       NotchState  = .closed
    @Published var activeTab:        PanelTab    = .overview
    @Published var isHoveringPill:   Bool        = false
    @Published var availableAgents:  [AgentInfo] = []
    let wsClient   = WebSocketClient()
    let discovery  = AgentDiscovery()

    private var cancellables = Set<AnyCancellable>()

    init() {
        wsClient.objectWillChange
            .sink { [weak self] _ in self?.objectWillChange.send() }
            .store(in: &cancellables)
    }
}
