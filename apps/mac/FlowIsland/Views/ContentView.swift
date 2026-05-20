import SwiftUI
import AppKit

private let WEB_APP          = "http://localhost:13000"
private let PILL_W:  CGFloat = 200
private let PILL_H:  CGFloat = 37
private let PANEL_W: CGFloat = 540
private let PANEL_H: CGFloat = 500

// ContentView fills the NSPanel (always full-size, transparent).
// The morphing notchContent sits at the top and is the only visible element.
struct ContentView: View {
    @ObservedObject var store: AppStore

    var body: some View {
        ZStack(alignment: .top) {
            Color.clear   // fills panel — transparent, no hit-testing
            NotchMorphView(store: store)
        }
    }
}

// MARK: - Dynamic Island morph

struct NotchMorphView: View {
    @ObservedObject var store: AppStore

    private var isOpen: Bool { store.notchState == .open }

    var body: some View {
        VStack(spacing: 0) {
            pillRow
                .frame(height: PILL_H)

            panelBody
                .frame(height: PANEL_H - PILL_H)
                .opacity(isOpen ? 1 : 0)
                .animation(
                    isOpen
                        ? .easeIn(duration: 0.12).delay(0.08)
                        : .easeOut(duration: 0.08),
                    value: isOpen
                )
        }
        .frame(
            width:  isOpen ? PANEL_W : PILL_W,
            height: isOpen ? PANEL_H  : PILL_H,
            alignment: .top
        )
        .background(morphBackground)
        .clipShape(
            NotchShape(
                topRadius:    isOpen ? 20 : 8,
                bottomRadius: isOpen ? 24 : 20
            )
        )
        .shadow(color: isOpen ? .black.opacity(0.55) : .clear, radius: 22, y: 12)
        .animation(
            isOpen
                ? .spring(response: 0.42, dampingFraction: 0.8)
                : .spring(response: 0.45, dampingFraction: 1.0),
            value: store.notchState
        )
    }

    // MARK: - Background (black pill → dark glass panel)

    @ViewBuilder
    private var morphBackground: some View {
        ZStack {
            Color.black
            VisualEffectBackground()
                .opacity(isOpen ? 1 : 0)
                .animation(.easeInOut(duration: 0.18), value: isOpen)
        }
    }

    // MARK: - Pill row

    private var pillRow: some View {
        HStack(spacing: 7) {
            Circle()
                .fill(store.wsClient.isConnected ? Color.green : Color(nsColor: .systemGray))
                .frame(width: 7, height: 7)
                .shadow(color: store.wsClient.isConnected ? .green.opacity(0.8) : .clear, radius: 4)

            Text("Flow")
                .font(.system(size: 13, weight: .bold))
                .foregroundColor(.white)
                .tracking(-0.5)

            if store.wsClient.agentState != .idle {
                Text(store.wsClient.agentState.emoji)
                    .font(.system(size: 11))
                    .foregroundColor(store.wsClient.agentState.color)
            }
        }
        .padding(.horizontal, 16)
        .frame(maxWidth: .infinity)
    }

    // MARK: - Expanded panel

    private var panelBody: some View {
        VStack(spacing: 0) {
            headerRow
            if !store.wsClient.isConnected { noAgentBanner }
            skillGraphSection
            Divider().opacity(0.15).padding(.horizontal, 16)
            eventFeedSection
            footerRow
        }
    }

    // MARK: Header

    private var headerRow: some View {
        HStack(spacing: 8) {
            Circle()
                .fill(store.wsClient.isConnected
                      ? Color.green
                      : Color(nsColor: .systemGray).opacity(0.4))
                .frame(width: 7, height: 7)
                .shadow(color: store.wsClient.isConnected ? .green.opacity(0.7) : .clear, radius: 4)

            Text("Flow")
                .font(.system(size: 13, weight: .bold))
                .foregroundColor(.white)

            if let id = store.wsClient.currentAgentId {
                Text(String(id.prefix(8)) + "…")
                    .font(.system(size: 9, design: .monospaced))
                    .foregroundColor(Color(nsColor: .systemGray))
            }

            Spacer()

            stateBadge
            openButton
            quitButton
        }
        .padding(.horizontal, 16)
        .padding(.top, 12)
        .padding(.bottom, 10)
        .overlay(Divider().opacity(0.1), alignment: .bottom)
    }

    private var stateBadge: some View {
        Text(store.wsClient.agentState.label)
            .font(.system(size: 10, weight: .semibold))
            .foregroundColor(store.wsClient.agentState.color)
            .padding(.horizontal, 8)
            .padding(.vertical, 2)
            .background(store.wsClient.agentState.color.opacity(0.08))
            .overlay(Capsule().stroke(store.wsClient.agentState.color.opacity(0.2), lineWidth: 1))
            .clipShape(Capsule())
    }

    private var openButton: some View {
        Button("↗ Open") {
            NSWorkspace.shared.open(URL(string: WEB_APP)!)
        }
        .buttonStyle(GlassButtonStyle(accent: true))
    }

    private var quitButton: some View {
        Button("✕") { NSApplication.shared.terminate(nil) }
            .buttonStyle(GlassButtonStyle(accent: false))
            .help("Quit Flow")
    }

    // MARK: No-agent banner

    private var noAgentBanner: some View {
        Text("No agent connected — start a Flow agent to see live data")
            .font(.system(size: 11))
            .foregroundColor(Color(nsColor: .systemGray))
            .padding(.horizontal, 10)
            .padding(.vertical, 8)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(Color.red.opacity(0.06))
            .overlay(RoundedRectangle(cornerRadius: 8).stroke(Color.red.opacity(0.15), lineWidth: 1))
            .padding(.horizontal, 16)
            .padding(.top, 8)
    }

    // MARK: Skill graph

    private var skillGraphSection: some View {
        VStack(alignment: .leading, spacing: 6) {
            sectionLabel("Skill graph")
            SkillGraphView(skills: store.wsClient.skills)
                .frame(height: 130)
        }
        .padding(.horizontal, 16)
        .padding(.top, 10)
        .padding(.bottom, 4)
    }

    // MARK: Event feed

    private var eventFeedSection: some View {
        VStack(alignment: .leading, spacing: 6) {
            sectionLabel("Live events")
            EventFeedView(events: store.wsClient.events)
                .frame(height: 150)
        }
        .padding(.horizontal, 16)
        .padding(.top, 8)
        .padding(.bottom, 10)
    }

    // MARK: Footer

    private var footerRow: some View {
        HStack(spacing: 5) {
            footerBtn("This Agent",
                      store.wsClient.currentAgentId.map { "/agents/\($0)" } ?? "/agents")
            footerBtn("Runs",
                      store.wsClient.currentAgentId.map { "/agents/\($0)/executions" } ?? "/executions")
            footerBtn("Memory",
                      store.wsClient.currentAgentId.map { "/agents/\($0)/memory" } ?? "/memory")
        }
        .padding(.horizontal, 16)
        .padding(.top, 6)
        .padding(.bottom, 14)
        .overlay(Divider().opacity(0.08), alignment: .top)
    }

    private func footerBtn(_ label: String, _ path: String) -> some View {
        Button(label) { NSWorkspace.shared.open(URL(string: WEB_APP + path)!) }
            .buttonStyle(FooterButtonStyle())
    }

    private func sectionLabel(_ text: String) -> some View {
        Text(text.uppercased())
            .font(.system(size: 9, weight: .bold))
            .foregroundColor(Color(nsColor: .systemGray).opacity(0.7))
            .tracking(1.2)
    }
}

// MARK: - NSVisualEffectView wrapper

struct VisualEffectBackground: NSViewRepresentable {
    func makeNSView(context: Context) -> NSVisualEffectView {
        let v = NSVisualEffectView()
        v.material      = .hudWindow
        v.blendingMode  = .behindWindow
        v.state         = .active
        v.appearance    = NSAppearance(named: .darkAqua)
        return v
    }
    func updateNSView(_ nsView: NSVisualEffectView, context: Context) {}
}

// MARK: - Button styles

struct GlassButtonStyle: ButtonStyle {
    let accent: Bool
    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(.system(size: 11, weight: .semibold))
            .foregroundColor(accent
                             ? Color(red: 0.65, green: 0.71, blue: 0.99)
                             : Color(nsColor: .systemGray))
            .padding(.horizontal, 10)
            .padding(.vertical, 4)
            .background(RoundedRectangle(cornerRadius: 8)
                .fill(accent
                      ? Color(red: 0.39, green: 0.4, blue: 0.96).opacity(configuration.isPressed ? 0.35 : 0.18)
                      : Color.white.opacity(configuration.isPressed ? 0.1 : 0.05)))
            .overlay(RoundedRectangle(cornerRadius: 8)
                .stroke(accent
                        ? Color(red: 0.39, green: 0.4, blue: 0.96).opacity(0.4)
                        : Color.white.opacity(0.1), lineWidth: 1))
    }
}

struct FooterButtonStyle: ButtonStyle {
    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(.system(size: 10, weight: .semibold))
            .foregroundColor(configuration.isPressed
                             ? Color(red: 0.65, green: 0.71, blue: 0.99)
                             : Color(nsColor: .systemGray))
            .frame(maxWidth: .infinity)
            .padding(.vertical, 6)
            .background(RoundedRectangle(cornerRadius: 8)
                .fill(Color.white.opacity(configuration.isPressed ? 0.08 : 0.04)))
            .overlay(RoundedRectangle(cornerRadius: 8)
                .stroke(Color.white.opacity(0.07), lineWidth: 1))
    }
}
