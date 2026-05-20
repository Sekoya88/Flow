import SwiftUI
import Foundation

private let SKILL_API = "http://localhost:18000/api/v1/local"

// Indigo matches web NODE_COLORS["agent"] = #6366f1
private let indigo   = Color(red: 0.388, green: 0.400, blue: 0.945)
// Cyan matches web NODE_COLORS["skill"] = #22d3ee
private let skillCyan = Color(red: 0.133, green: 0.827, blue: 0.933)
// Violet for reflecting state
private let violet   = Color(red: 0.655, green: 0.545, blue: 0.973)

struct SkillNode {
    let id: String
    let name: String
    var score: Double   // 0..1 bandit reward
    var active: Bool
}

// MARK: - Layout helpers

private func radialPositions(count: Int, size: CGSize) -> [CGPoint] {
    guard count > 0 else { return [] }
    let cx = size.width / 2, cy = size.height / 2
    if count == 1 { return [CGPoint(x: cx, y: cy)] }

    // Tight orbit — leaves room for node radius (~16px) + label (~12px) on all sides
    let rw = min(size.width  * 0.26, 130.0)
    let rh = min(size.height * 0.26, 36.0)
    var pts: [CGPoint] = []
    for i in 0..<count {
        let angle = (Double(i) / Double(count)) * 2.0 * Double.pi - Double.pi / 2.0
        let x = cx + Foundation.cos(angle) * rw
        let y = cy + Foundation.sin(angle) * rh
        pts.append(CGPoint(x: x, y: y))
    }
    return pts
}

// MARK: - SkillGraphView

struct SkillGraphView: View {
    let wsSkills: [SkillNode]   // live from WebSocket events
    let agentId:  String?       // for DB fallback when idle

    @State private var dbSkills: [SkillNode] = []
    @State private var isLoading = false

    private var displaySkills: [SkillNode] { wsSkills.isEmpty ? dbSkills : wsSkills }

    var body: some View {
        Group {
            if isLoading {
                loadingState
            } else if displaySkills.isEmpty {
                emptyState
            } else {
                graphCanvas
            }
        }
        .onAppear { fetchFromDB() }
        .onChange(of: agentId) { _ in fetchFromDB() }
    }

    // MARK: Loading

    private var loadingState: some View {
        VStack(spacing: 6) {
            ProgressView().scaleEffect(0.6)
            Text("Loading skills…")
                .font(.system(size: 9))
                .foregroundColor(Color(nsColor: .systemGray).opacity(0.4))
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }

    // MARK: Empty

    private var emptyState: some View {
        VStack(spacing: 5) {
            Image(systemName: "sparkles")
                .font(.system(size: 20))
                .foregroundColor(indigo.opacity(0.3))
            Text("No skills configured")
                .font(.system(size: 10, weight: .medium))
                .foregroundColor(Color(nsColor: .systemGray).opacity(0.45))
            Text("Add skills in the Flow dashboard")
                .font(.system(size: 9))
                .foregroundColor(Color(nsColor: .systemGray).opacity(0.25))
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }

    // MARK: Graph

    private var graphCanvas: some View {
        GeometryReader { geo in
            ZStack {
                // Starfield background
                Canvas { ctx, size in
                    drawStarfield(ctx: ctx, size: size)
                }

                // Main graph
                Canvas { ctx, size in
                    let skills = displaySkills.prefix(11)
                    let skillPts = radialPositions(count: skills.count, size: size)
                    let center   = CGPoint(x: size.width / 2, y: size.height / 2)

                    // Draw edges first (behind nodes)
                    for pt in skillPts {
                        var path = Path()
                        path.move(to: center)
                        path.addLine(to: pt)
                        ctx.stroke(path,
                                   with: .color(skillCyan.opacity(0.18)),
                                   lineWidth: 0.8)
                    }

                    // Skill nodes
                    for (i, skill) in skills.enumerated() {
                        let pt = skillPts[i]
                        let r  = 9.0 + skill.score * 7.0
                        drawNode(ctx: ctx, pt: pt, r: r, color: skillCyan,
                                 active: skill.active, score: skill.score)
                    }

                    // Agent center node (always on top)
                    drawAgentNode(ctx: ctx, center: center)
                }

                // Labels overlay (SwiftUI text is crisp; Canvas text isn't)
                labelsLayer(geo: geo)
            }
        }
    }

    // MARK: Drawing primitives

    private func drawStarfield(ctx: GraphicsContext, size: CGSize) {
        // Tiny random dots for depth
        let seeds: [(Double, Double, Double)] = [
            (0.15, 0.22, 0.35), (0.78, 0.12, 0.25), (0.35, 0.88, 0.30),
            (0.62, 0.55, 0.20), (0.22, 0.64, 0.25), (0.88, 0.78, 0.35),
            (0.45, 0.15, 0.20), (0.10, 0.48, 0.30), (0.92, 0.35, 0.25),
            (0.55, 0.72, 0.20), (0.30, 0.40, 0.15), (0.70, 0.25, 0.30),
        ]
        for (rx, ry, alpha) in seeds {
            let pt = CGPoint(x: rx * size.width, y: ry * size.height)
            let dot = Path(ellipseIn: CGRect(x: pt.x - 1, y: pt.y - 1, width: 2, height: 2))
            ctx.fill(dot, with: .color(.white.opacity(alpha)))
        }
    }

    private func drawAgentNode(ctx: GraphicsContext, center: CGPoint) {
        let r: Double = 16
        // Outer glow
        for (gr, galpha) in [(28.0, 0.06), (22.0, 0.12)] {
            let glow = Path(ellipseIn: CGRect(x: center.x - gr, y: center.y - gr,
                                              width: gr * 2, height: gr * 2))
            ctx.fill(glow, with: .color(indigo.opacity(galpha)))
        }
        // Fill
        let circle = Path(ellipseIn: CGRect(x: center.x - r, y: center.y - r,
                                            width: r * 2, height: r * 2))
        ctx.fill(circle, with: .color(indigo.opacity(0.75)))
        ctx.stroke(circle, with: .color(indigo.opacity(0.9)), lineWidth: 1.5)
        // Inner bright center
        let inner = Path(ellipseIn: CGRect(x: center.x - 4, y: center.y - 4, width: 8, height: 8))
        ctx.fill(inner, with: .color(.white.opacity(0.25)))
    }

    private func drawNode(ctx: GraphicsContext, pt: CGPoint, r: Double,
                          color: Color, active: Bool, score: Double) {
        let glowAlpha = active ? 0.22 : 0.06
        // Glow halo
        let halo = Path(ellipseIn: CGRect(x: pt.x - r - 6, y: pt.y - r - 6,
                                          width: (r + 6) * 2, height: (r + 6) * 2))
        ctx.fill(halo, with: .color(color.opacity(glowAlpha)))

        // Node fill
        let fillAlpha = active ? (0.45 + score * 0.4) : 0.2
        let circle = Path(ellipseIn: CGRect(x: pt.x - r, y: pt.y - r, width: r * 2, height: r * 2))
        ctx.fill(circle, with: .color(color.opacity(fillAlpha)))

        // Border
        let borderAlpha = active ? 0.85 : 0.35
        ctx.stroke(circle, with: .color(color.opacity(borderAlpha)), lineWidth: active ? 1.2 : 0.8)

        // Score arc at bottom
        if score > 0.1 {
            let barW = (r * 2 - 4) * score
            let bar  = Path(roundedRect: CGRect(x: pt.x - r + 2, y: pt.y + r - 4,
                                                width: barW, height: 2.5), cornerRadius: 1.5)
            ctx.fill(bar, with: .color(color.opacity(active ? 0.8 : 0.3)))
        }
    }

    // MARK: Labels layer

    private func labelsLayer(geo: GeometryProxy) -> some View {
        let skills = Array(displaySkills.prefix(11))
        let pts    = radialPositions(count: skills.count, size: geo.size)
        let center = CGPoint(x: geo.size.width / 2, y: geo.size.height / 2)

        return ZStack {
            // Agent label
            Text("agent")
                .font(.system(size: 7, weight: .bold))
                .foregroundColor(.white.opacity(0.5))
                .position(x: center.x, y: center.y + 22)

            // Skill labels
            ForEach(Array(skills.enumerated()), id: \.offset) { i, skill in
                let pt    = pts[i]
                let label = skill.name.count > 13 ? String(skill.name.prefix(12)) + "…" : skill.name

                // Push label outward from center, clamped to stay within canvas
                let dx    = pt.x - center.x
                let dy    = pt.y - center.y
                let len   = max(sqrt(dx * dx + dy * dy), 1)
                let push: Double = 14
                let rawLx = pt.x + (dx / len) * push
                let rawLy = pt.y + (dy / len) * push + 4
                let lx    = max(30, min(geo.size.width  - 30, rawLx))
                let ly    = max(10, min(geo.size.height - 10, rawLy))

                Text(label)
                    .font(.system(size: 7.5, weight: skill.active ? .bold : .regular))
                    .foregroundColor(skill.active
                                     ? skillCyan.opacity(0.95)
                                     : Color(nsColor: .systemGray).opacity(0.5))
                    .position(x: lx, y: ly)
                    .shadow(color: skill.active ? skillCyan.opacity(0.4) : .clear, radius: 3)
            }
        }
    }

    // MARK: DB fetch

    private func fetchFromDB() {
        guard let id = agentId,
              let url = URL(string: "\(SKILL_API)/agent-skills/\(id)") else { return }
        isLoading = true
        URLSession.shared.dataTask(with: url) { data, _, _ in
            let skills = (data.flatMap { try? JSONSerialization.jsonObject(with: $0) as? [String: Any] })
                .flatMap { $0["skills"] as? [[String: Any]] } ?? []
            let nodes = skills.compactMap { dict -> SkillNode? in
                guard let sid  = dict["id"]   as? String,
                      let name = dict["name"] as? String else { return nil }
                return SkillNode(id: sid, name: name, score: dict["score"] as? Double ?? 0.5, active: false)
            }
            DispatchQueue.main.async {
                self.dbSkills  = nodes
                self.isLoading = false
            }
        }.resume()
    }
}
