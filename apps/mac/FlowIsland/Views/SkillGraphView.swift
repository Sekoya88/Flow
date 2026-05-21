import SwiftUI
import Foundation

private let GRAPH_API = "http://localhost:18000/api/v1/local"

// MARK: - SkillNode (shared with WebSocketClient)

struct SkillNode: Equatable {
    let id: String
    let name: String
    var score: Double
    var active: Bool
}

// MARK: - Color palette

private let colorAgent        = Color(red: 0.388, green: 0.400, blue: 0.945) // #6366f1
private let colorSkill        = Color(red: 0.133, green: 0.827, blue: 0.933) // #22d3ee
private let colorTool         = Color(red: 0.133, green: 0.773, blue: 0.368) // #22c55e
private let colorSystemPrompt = Color(red: 0.627, green: 0.478, blue: 0.929) // #a178ed
private let colorMetacog      = Color(red: 0.655, green: 0.545, blue: 0.973) // #a78bfa
private let colorMemory       = Color(red: 0.949, green: 0.749, blue: 0.286) // #f2bf49

// MARK: - Graph data models

enum GraphNodeType { case agent, skill, tool, systemPrompt, metacog, memory }

struct GraphNode: Identifiable, Equatable {
    let id: String
    let label: String
    let type: GraphNodeType
    var x: Double
    var y: Double
    var vx: Double = 0
    var vy: Double = 0
    var pinned: Bool = false
    var active: Bool = false
    var score: Double = 0.5

    var color: Color {
        switch type {
        case .agent:        return colorAgent
        case .skill:        return colorSkill
        case .tool:         return colorTool
        case .systemPrompt: return colorSystemPrompt
        case .metacog:      return colorMetacog
        case .memory:       return colorMemory
        }
    }

    var radius: Double {
        switch type {
        case .agent:               return 15
        case .skill:               return 8 + score * 5
        case .tool, .systemPrompt,
             .metacog, .memory:    return 7
        }
    }

    var typeLabel: String {
        switch type {
        case .agent:        return "Agent"
        case .skill:        return "Skill"
        case .tool:         return "Tool"
        case .systemPrompt: return "System Prompt"
        case .metacog:      return "Meta-Cognition"
        case .memory:       return "Memory"
        }
    }

    static func == (lhs: GraphNode, rhs: GraphNode) -> Bool {
        lhs.id == rhs.id && lhs.x == rhs.x && lhs.y == rhs.y && lhs.active == rhs.active
    }
}

struct GraphEdge: Identifiable {
    let id: String
    let sourceId: String
    let targetId: String
    let dashed: Bool
}

// MARK: - API response

struct AgentGraphResponse: Decodable {
    struct AgentInfo: Decodable { let id: String; let name: String; let template: String }
    struct SkillInfo: Decodable { let id: String; let name: String; let score: Double; let useCount: Int; let category: String }
    let agent: AgentInfo?
    let skills: [SkillInfo]
    let tools: [String]
    let hasSystemPrompt: Bool
    let memoryCount: Int
}

// MARK: - Force simulation engine

class ForceGraph: ObservableObject {
    @Published var nodes: [GraphNode] = []
    var edges: [GraphEdge] = []
    var canvasSize: CGSize = .zero
    var timer: Timer?
    private var tickCount = 0

    func startSimulation() {
        tickCount = 0
        timer?.invalidate()
        timer = Timer.scheduledTimer(withTimeInterval: 1.0 / 60.0, repeats: true) { [weak self] _ in
            self?.tick()
        }
    }

    func stopSimulation() {
        timer?.invalidate()
        timer = nil
    }

    private func tick() {
        guard !nodes.isEmpty, canvasSize.width > 0 else { return }
        tickCount += 1
        let cx = canvasSize.width / 2
        let cy = canvasSize.height / 2
        let pad: Double = 28
        var n = nodes

        // Repulsion (all pairs)
        for i in 0..<n.count {
            for j in (i + 1)..<n.count {
                let dx = n[j].x - n[i].x
                let dy = n[j].y - n[i].y
                let dist2 = dx * dx + dy * dy
                guard dist2 > 0 else { continue }
                let dist = sqrt(dist2)
                let minDist = n[i].radius + n[j].radius + 34
                if dist < minDist * 2.5 {
                    let force = min(120.0 / dist2, 4.0)
                    let nx = dx / dist; let ny = dy / dist
                    if !n[i].pinned { n[i].vx -= nx * force; n[i].vy -= ny * force }
                    if !n[j].pinned { n[j].vx += nx * force; n[j].vy += ny * force }
                }
            }
        }

        // Spring attraction along edges
        let restLen: Double = 70
        let springK: Double = 0.055
        for edge in edges {
            guard let si = n.firstIndex(where: { $0.id == edge.sourceId }),
                  let ti = n.firstIndex(where: { $0.id == edge.targetId }) else { continue }
            let dx = n[ti].x - n[si].x
            let dy = n[ti].y - n[si].y
            let dist = max(sqrt(dx * dx + dy * dy), 0.1)
            let force = (dist - restLen) * springK
            let nx = dx / dist; let ny = dy / dist
            if !n[si].pinned { n[si].vx += nx * force; n[si].vy += ny * force }
            if !n[ti].pinned { n[ti].vx -= nx * force; n[ti].vy -= ny * force }
        }

        // Weak center gravity
        for i in 0..<n.count {
            guard !n[i].pinned else { continue }
            n[i].vx += (cx - n[i].x) * 0.003
            n[i].vy += (cy - n[i].y) * 0.003
        }

        // Damping + integrate + boundary clamp
        for i in 0..<n.count {
            guard !n[i].pinned else { continue }
            n[i].vx *= 0.82; n[i].vy *= 0.82
            n[i].x = max(pad, min(canvasSize.width - pad, n[i].x + n[i].vx))
            n[i].y = max(pad, min(canvasSize.height - pad, n[i].y + n[i].vy))
        }

        nodes = n

        // Cool down after stable
        if tickCount > 300 {
            let maxSpeed = n.map { abs($0.vx) + abs($0.vy) }.max() ?? 0
            if maxSpeed < 0.3 { stopSimulation() }
        }
    }

    func rebuild(response: AgentGraphResponse, canvasSize: CGSize) {
        stopSimulation()
        self.canvasSize = canvasSize
        let cx = canvasSize.width / 2
        let cy = canvasSize.height / 2

        var newNodes: [GraphNode] = []
        var newEdges: [GraphEdge] = []
        let agentId = response.agent?.id ?? "agent"

        newNodes.append(GraphNode(id: agentId,
                                   label: response.agent?.name ?? "Agent",
                                   type: .agent, x: cx, y: cy))

        for skill in response.skills {
            let angle = Double.random(in: 0 ..< (2 * .pi))
            let r = Double.random(in: 60...85)
            newNodes.append(GraphNode(id: skill.id, label: skill.name, type: .skill,
                                       x: cx + Darwin.cos(angle) * r,
                                       y: cy + Darwin.sin(angle) * r,
                                       score: skill.score))
            newEdges.append(GraphEdge(id: "esk-\(skill.id)", sourceId: agentId,
                                       targetId: skill.id, dashed: true))
        }

        for (i, tool) in response.tools.enumerated() {
            let tc = max(response.tools.count, 1)
            let angle = (Double(i) / Double(tc)) * 2 * .pi + .pi / 6
            let r = Double.random(in: 80...120)
            let nid = "tool-\(tool)"
            newNodes.append(GraphNode(id: nid,
                                       label: tool.replacingOccurrences(of: "_", with: " "),
                                       type: .tool,
                                       x: cx + Darwin.cos(angle) * r,
                                       y: cy + Darwin.sin(angle) * r))
            newEdges.append(GraphEdge(id: "etool-\(tool)", sourceId: agentId,
                                       targetId: nid, dashed: false))
        }

        if response.hasSystemPrompt {
            newNodes.append(GraphNode(id: "sysprompt", label: "System Prompt",
                                       type: .systemPrompt,
                                       x: cx + Darwin.cos(.pi * 0.7) * 95,
                                       y: cy + Darwin.sin(.pi * 0.7) * 95))
            newEdges.append(GraphEdge(id: "esysprompt", sourceId: agentId,
                                       targetId: "sysprompt", dashed: false))
        }

        newNodes.append(GraphNode(id: "metacog", label: "Meta-Cog", type: .metacog,
                                   x: cx + Darwin.cos(.pi * 1.35) * 90,
                                   y: cy + Darwin.sin(.pi * 1.35) * 90))
        newEdges.append(GraphEdge(id: "emetacog", sourceId: agentId,
                                   targetId: "metacog", dashed: true))

        if response.memoryCount > 0 {
            newNodes.append(GraphNode(id: "memory",
                                       label: "\(response.memoryCount) mem",
                                       type: .memory,
                                       x: cx + Darwin.cos(.pi * 0.2) * 90,
                                       y: cy + Darwin.sin(.pi * 0.2) * 90))
            newEdges.append(GraphEdge(id: "ememory", sourceId: agentId,
                                       targetId: "memory", dashed: false))
        }

        edges = newEdges
        nodes = newNodes
        startSimulation()
    }

    func updateActiveSkills(_ activeNames: Set<String>) {
        for i in 0..<nodes.count where nodes[i].type == .skill {
            nodes[i].active = activeNames.contains(nodes[i].label)
        }
    }
}

// MARK: - SkillGraphView

struct SkillGraphView: View {
    @ObservedObject var wsClient: WebSocketClient

    private var agentId: String? { wsClient.currentAgentId }
    private var wsSkills: [SkillNode] { wsClient.skills }

    @StateObject private var graph = ForceGraph()
    @State private var isLoading = false
    @State private var fetchError = false
    @State private var selectedNode: GraphNode?
    @State private var draggedNodeId: String?
    @State private var isDraggingNode = false
    @State private var panOffset = CGSize.zero
    @State private var panBase = CGSize.zero
    @State private var zoom: Double = 1.0
    @State private var canvasSize = CGSize.zero

    var body: some View {
        Group {
            if isLoading {
                loadingState
            } else if fetchError {
                errorState
            } else if graph.nodes.isEmpty {
                emptyState
            } else {
                graphView
            }
        }
        .onAppear { fetchGraph() }
        .onChange(of: agentId) { _ in fetchGraph() }
        .onChange(of: wsSkills) { newSkills in
            let active = Set(newSkills.filter(\.active).map(\.name))
            graph.updateActiveSkills(active)
            if graph.timer == nil { graph.startSimulation() }
        }
        .onDisappear { graph.stopSimulation() }
    }

    // MARK: State views

    private var loadingState: some View {
        VStack(spacing: 6) {
            ProgressView().scaleEffect(0.6)
            Text("Loading graph…")
                .font(.system(size: 9))
                .foregroundColor(Color(nsColor: .systemGray).opacity(0.4))
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }

    private var emptyState: some View {
        VStack(spacing: 5) {
            Image(systemName: "sparkles")
                .font(.system(size: 20))
                .foregroundColor(colorAgent.opacity(0.3))
            Text(agentId == nil ? "Select an agent" : "No graph data")
                .font(.system(size: 10, weight: .medium))
                .foregroundColor(Color(nsColor: .systemGray).opacity(0.45))
            Text(agentId == nil ? "Pick an agent from the menu above" : "Add skills in the Flow dashboard")
                .font(.system(size: 9))
                .foregroundColor(Color(nsColor: .systemGray).opacity(0.25))
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }

    private var errorState: some View {
        VStack(spacing: 6) {
            Image(systemName: "exclamationmark.triangle")
                .font(.system(size: 16))
                .foregroundColor(Color.orange.opacity(0.6))
            Text("Graph unavailable")
                .font(.system(size: 10, weight: .medium))
                .foregroundColor(Color(nsColor: .systemGray).opacity(0.45))
            Button("Retry") { fetchGraph() }
                .font(.system(size: 9))
                .foregroundColor(colorAgent)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }

    // MARK: Graph view

    private var graphView: some View {
        GeometryReader { geo in
            ZStack {
                // Edges
                Canvas { ctx, _ in drawEdges(ctx: ctx) }
                    .allowsHitTesting(false)

                // Nodes
                Canvas { ctx, _ in
                    for node in graph.nodes { drawNode(ctx: ctx, node: node) }
                }
                .allowsHitTesting(false)

                // Labels
                ZStack {
                    ForEach(graph.nodes) { node in nodeLabel(node: node) }
                }
                .allowsHitTesting(false)

                // Popover
                if let sel = selectedNode,
                   let node = graph.nodes.first(where: { $0.id == sel.id }) {
                    nodePopover(node: node, canvasSize: geo.size)
                        .animation(.easeOut(duration: 0.15), value: sel.id)
                }

                // Legend
                legendView
                    .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .bottomLeading)
                    .padding(.leading, 8).padding(.bottom, 6)
                    .allowsHitTesting(false)
            }
            .clipped()
            .scaleEffect(zoom, anchor: .center)
            .offset(panOffset)
            .contentShape(Rectangle())
            .gesture(
                DragGesture(minimumDistance: 2)
                    .onChanged { val in handleDrag(val, canvasSize: geo.size) }
                    .onEnded   { _   in handleDragEnd() }
            )
            .gesture(
                MagnificationGesture()
                    .onChanged { scale in zoom = max(0.4, min(3.0, scale)) }
            )
            .onTapGesture { loc in handleTap(at: loc) }
            .onAppear {
                canvasSize = geo.size
                graph.canvasSize = geo.size
            }
            .onChange(of: geo.size) { sz in
                canvasSize = sz
                graph.canvasSize = sz
            }
        }
    }

    // MARK: Gesture handlers

    private func handleDrag(_ val: DragGesture.Value, canvasSize: CGSize) {
        if !isDraggingNode && draggedNodeId == nil {
            let loc = val.startLocation
            if let idx = nearestNode(to: loc, within: 22) {
                isDraggingNode = true
                draggedNodeId = graph.nodes[idx].id
                graph.nodes[idx].pinned = true
                if graph.timer == nil { graph.startSimulation() }
            } else {
                panBase = panOffset
            }
        }

        if isDraggingNode, let nodeId = draggedNodeId,
           let idx = graph.nodes.firstIndex(where: { $0.id == nodeId }) {
            graph.nodes[idx].x = Double(val.location.x)
            graph.nodes[idx].y = Double(val.location.y)
            graph.nodes[idx].vx = 0
            graph.nodes[idx].vy = 0
        } else if !isDraggingNode {
            panOffset = CGSize(
                width: panBase.width + val.translation.width,
                height: panBase.height + val.translation.height
            )
        }
    }

    private func handleDragEnd() {
        if let nodeId = draggedNodeId,
           let idx = graph.nodes.firstIndex(where: { $0.id == nodeId }) {
            graph.nodes[idx].pinned = false
        }
        isDraggingNode = false
        draggedNodeId = nil
    }

    private func handleTap(at location: CGPoint) {
        if let idx = nearestNode(to: location, within: 22) {
            let node = graph.nodes[idx]
            selectedNode = (selectedNode?.id == node.id) ? nil : node
        } else {
            selectedNode = nil
        }
    }

    private func nearestNode(to point: CGPoint, within extra: Double) -> Int? {
        var best: (Int, Double)?
        for (i, node) in graph.nodes.enumerated() {
            let dx = node.x - Double(point.x)
            let dy = node.y - Double(point.y)
            let dist = sqrt(dx * dx + dy * dy)
            if dist < node.radius + extra {
                if best == nil || dist < best!.1 { best = (i, dist) }
            }
        }
        return best?.0
    }

    // MARK: Canvas drawing

    private func drawEdges(ctx: GraphicsContext) {
        for edge in graph.edges {
            guard let s = graph.nodes.first(where: { $0.id == edge.sourceId }),
                  let t = graph.nodes.first(where: { $0.id == edge.targetId }) else { continue }
            var path = Path()
            path.move(to: CGPoint(x: s.x, y: s.y))
            path.addLine(to: CGPoint(x: t.x, y: t.y))
            let alpha = t.active ? 0.35 : 0.10
            if edge.dashed {
                ctx.stroke(path, with: .color(t.color.opacity(alpha)),
                           style: StrokeStyle(lineWidth: 0.75, dash: [4, 4]))
            } else {
                ctx.stroke(path, with: .color(t.color.opacity(alpha)), lineWidth: 0.75)
            }
        }
    }

    private func drawNode(ctx: GraphicsContext, node: GraphNode) {
        let r = node.radius
        let pt = CGPoint(x: node.x, y: node.y)
        let color = node.color
        let isAgent = node.type == .agent
        let lit = node.active || isAgent

        // Single-layer subtle glow
        let gr = r + 5
        let glowA = isAgent ? 0.12 : (lit ? 0.14 : 0.04)
        ctx.fill(Path(ellipseIn: CGRect(x: pt.x-gr, y: pt.y-gr, width: gr*2, height: gr*2)),
                 with: .color(color.opacity(glowA)))

        // Fill + 1px stroke at 60% opacity
        let fillA = isAgent ? 0.80 : (lit ? 0.55 : 0.22)
        let circle = Path(ellipseIn: CGRect(x: pt.x-r, y: pt.y-r, width: r*2, height: r*2))
        ctx.fill(circle, with: .color(color.opacity(fillA)))
        ctx.stroke(circle, with: .color(color.opacity(0.60)), lineWidth: 1.0)

        if isAgent {
            ctx.fill(Path(ellipseIn: CGRect(x: pt.x-4, y: pt.y-4, width: 8, height: 8)),
                     with: .color(.white.opacity(0.25)))
        }
    }

    // MARK: Labels overlay

    @ViewBuilder
    private func nodeLabel(node: GraphNode) -> some View {
        if node.type == .agent || selectedNode?.id == node.id {
            let isAgent = node.type == .agent
            Text(node.label.count > 13 ? String(node.label.prefix(12)) + "…" : node.label)
                .font(.system(size: isAgent ? 8 : 7.5, weight: .semibold, design: .monospaced))
                .foregroundColor(.white.opacity(0.75))
                .position(x: node.x, y: node.y + (isAgent ? 22 : node.radius + 11))
                .animation(.none, value: node.x)
                .animation(.none, value: node.y)
        }
    }

    // MARK: Node popover

    private func nodePopover(node: GraphNode, canvasSize: CGSize) -> some View {
        let pw: Double = 136, ph: Double = 56
        let rawX = node.x + 20, rawY = node.y - 32
        let px = max(pw/2 + 6, min(Double(canvasSize.width) - pw/2 - 6, rawX + pw/2))
        let py = max(ph/2 + 6, min(Double(canvasSize.height) - ph/2 - 6, rawY + ph/2))

        return VStack(alignment: .leading, spacing: 3) {
            HStack(spacing: 4) {
                Circle().fill(node.color).frame(width: 6, height: 6)
                Text(node.typeLabel)
                    .font(.system(size: 7, weight: .semibold))
                    .foregroundColor(node.color.opacity(0.9))
            }
            Text(node.label)
                .font(.system(size: 8.5, weight: .medium))
                .foregroundColor(.white.opacity(0.85))
                .lineLimit(2)
            if node.type == .skill {
                Text("score: \(Int(node.score * 100))%")
                    .font(.system(size: 7))
                    .foregroundColor(Color(nsColor: .systemGray).opacity(0.6))
            }
        }
        .padding(.horizontal, 9).padding(.vertical, 7)
        .background(
            RoundedRectangle(cornerRadius: 7)
                .fill(Color(red: 0.08, green: 0.08, blue: 0.12).opacity(0.96))
                .overlay(RoundedRectangle(cornerRadius: 7)
                    .stroke(node.color.opacity(0.35), lineWidth: 0.8))
        )
        .frame(width: pw)
        .position(x: px, y: py)
        .zIndex(100)
    }

    // MARK: Legend

    private var legendView: some View {
        let items: [(String, Color)] = [
            ("Agent", colorAgent), ("Skill", colorSkill), ("Tool", colorTool),
            ("Prompt", colorSystemPrompt), ("Meta-Cog", colorMetacog), ("Memory", colorMemory),
        ]
        return VStack(alignment: .leading, spacing: 3) {
            ForEach(items, id: \.0) { label, color in
                HStack(spacing: 4) {
                    Circle().fill(color).frame(width: 5, height: 5)
                    Text(label).font(.system(size: 6.5))
                        .foregroundColor(Color(nsColor: .systemGray).opacity(0.45))
                }
            }
        }
        .padding(5)
        .background(Color.black.opacity(0.30))
        .cornerRadius(5)
    }

    // MARK: Fetch

    private func fetchGraph() {
        guard let id = agentId,
              let url = URL(string: "\(GRAPH_API)/agent-graph/\(id)") else {
            graph.nodes = []
            fetchError = false
            return
        }
        isLoading = true
        fetchError = false
        let decoder = JSONDecoder()
        decoder.keyDecodingStrategy = .convertFromSnakeCase
        URLSession.shared.dataTask(with: url) { data, response, error in
            DispatchQueue.main.async {
                self.isLoading = false
                guard error == nil,
                      let data,
                      let parsed = try? decoder.decode(AgentGraphResponse.self, from: data) else {
                    // Show error state so the user knows the fetch failed (not "no skills")
                    if self.graph.nodes.isEmpty { self.fetchError = true }
                    return
                }
                self.fetchError = false
                let size = self.canvasSize.width > 0 ? self.canvasSize : CGSize(width: 540, height: 200)
                self.graph.rebuild(response: parsed, canvasSize: size)
            }
        }.resume()
    }
}
