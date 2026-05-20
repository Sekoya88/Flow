import SwiftUI

struct SkillNode {
    let id: String
    let name: String
    var score: Double  // 0..1 bandit reward
    var active: Bool
}

struct SkillGraphView: View {
    let skills: [SkillNode]

    private static let positions: [CGPoint] = [
        CGPoint(x: 0,   y: 0),    // center
        CGPoint(x: 60,  y: 0),
        CGPoint(x: -60, y: 0),
        CGPoint(x: 0,   y: 48),
        CGPoint(x: 0,   y: -48),
        CGPoint(x: 48,  y: 38),
        CGPoint(x: -48, y: 38),
        CGPoint(x: 48,  y: -38),
    ]

    var body: some View {
        Group {
            if skills.isEmpty {
                emptyState
            } else {
                canvas
            }
        }
    }

    private var emptyState: some View {
        Text("No skills active yet")
            .font(.system(size: 11))
            .foregroundColor(Color(nsColor: .systemGray).opacity(0.5))
            .frame(maxWidth: .infinity, maxHeight: .infinity)
    }

    private var canvas: some View {
        Canvas { ctx, size in
            let cx = size.width / 2
            let cy = size.height / 2
            let nodes = skills.prefix(8).enumerated().map { (i, s) -> (SkillNode, CGPoint) in
                let base = Self.positions[i]
                return (s, CGPoint(x: cx + base.x, y: cy + base.y))
            }

            // Edges from center to each satellite
            if nodes.count > 1 {
                let center = nodes[0].1
                for (skill, pt) in nodes.dropFirst() {
                    var path = Path()
                    path.move(to: center)
                    path.addLine(to: pt)
                    let alpha = skill.active ? 0.25 : 0.1
                    ctx.stroke(path, with: .color(Color(red: 0.39, green: 0.4, blue: 0.96).opacity(alpha)), lineWidth: 1)
                }
            }

            // Nodes
            for (skill, pt) in nodes {
                let r = 14.0 + skill.score * 8.0
                let alpha = skill.active ? (0.4 + skill.score * 0.5) : 0.2
                let nodeColor = skill.active
                    ? Color(red: 0.39, green: 0.4, blue: 0.96).opacity(alpha)
                    : Color(nsColor: .systemGray).opacity(0.25)
                let borderColor = skill.active
                    ? Color(red: 0.65, green: 0.71, blue: 0.99).opacity(0.5)
                    : Color(nsColor: .systemGray).opacity(0.3)

                // Glow ring for active nodes
                if skill.active {
                    let glow = Path(ellipseIn: CGRect(x: pt.x - r - 5, y: pt.y - r - 5, width: (r + 5) * 2, height: (r + 5) * 2))
                    ctx.fill(glow, with: .color(Color(red: 0.39, green: 0.4, blue: 0.96).opacity(0.1)))
                }

                let circle = Path(ellipseIn: CGRect(x: pt.x - r, y: pt.y - r, width: r * 2, height: r * 2))
                ctx.fill(circle, with: .color(nodeColor))
                ctx.stroke(circle, with: .color(borderColor), lineWidth: 1)

                // Score bar
                let barW = (r * 2 - 4) * skill.score
                let barRect = CGRect(x: pt.x - r + 2, y: pt.y + r - 5, width: barW, height: 3)
                let bar = Path(roundedRect: barRect, cornerRadius: 1.5)
                ctx.fill(bar, with: .color(Color(red: 0.65, green: 0.71, blue: 0.99).opacity(0.7)))
            }
        }
        // Labels drawn as overlay (Canvas text rendering is limited)
        .overlay(labelsOverlay)
    }

    private var labelsOverlay: some View {
        GeometryReader { geo in
            let cx = geo.size.width / 2
            let cy = geo.size.height / 2
            ForEach(Array(skills.prefix(8).enumerated()), id: \.offset) { i, skill in
                let base = Self.positions[i]
                let pt = CGPoint(x: cx + base.x, y: cy + base.y)
                let label = skill.name.count > 10 ? String(skill.name.prefix(9)) + "…" : skill.name
                Text(label)
                    .font(.system(size: 7.5, weight: .semibold))
                    .foregroundColor(skill.active ? Color(red: 0.78, green: 0.82, blue: 0.99) : Color(nsColor: .systemGray).opacity(0.5))
                    .position(pt)
            }
        }
    }
}
