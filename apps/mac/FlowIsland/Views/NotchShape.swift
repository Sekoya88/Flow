import SwiftUI

// Animatable rounded-rect with independent top/bottom corner radii.
// When SwiftUI animates with .animation(), it interpolates topRadius and
// bottomRadius each frame via animatableData — producing the Dynamic Island
// "squish" morphing between pill and expanded panel.
struct NotchShape: Shape, Animatable {
    var topRadius:    CGFloat
    var bottomRadius: CGFloat

    var animatableData: AnimatablePair<CGFloat, CGFloat> {
        get { .init(topRadius, bottomRadius) }
        set { topRadius = newValue.first; bottomRadius = newValue.second }
    }

    func path(in rect: CGRect) -> Path {
        let t = min(topRadius,    min(rect.width, rect.height) / 2)
        let b = min(bottomRadius, min(rect.width, rect.height) / 2)
        var p = Path()
        p.move(to: CGPoint(x: rect.minX + t, y: rect.minY))
        p.addLine(to: CGPoint(x: rect.maxX - t, y: rect.minY))
        p.addArc(center: CGPoint(x: rect.maxX - t, y: rect.minY + t),
                 radius: t, startAngle: .degrees(-90), endAngle: .degrees(0),   clockwise: false)
        p.addLine(to: CGPoint(x: rect.maxX, y: rect.maxY - b))
        p.addArc(center: CGPoint(x: rect.maxX - b, y: rect.maxY - b),
                 radius: b, startAngle: .degrees(0),   endAngle: .degrees(90),  clockwise: false)
        p.addLine(to: CGPoint(x: rect.minX + b, y: rect.maxY))
        p.addArc(center: CGPoint(x: rect.minX + b, y: rect.maxY - b),
                 radius: b, startAngle: .degrees(90),  endAngle: .degrees(180), clockwise: false)
        p.addLine(to: CGPoint(x: rect.minX, y: rect.minY + t))
        p.addArc(center: CGPoint(x: rect.minX + t, y: rect.minY + t),
                 radius: t, startAngle: .degrees(180), endAngle: .degrees(270), clockwise: false)
        p.closeSubpath()
        return p
    }
}
