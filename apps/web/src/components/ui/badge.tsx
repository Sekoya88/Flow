import { mergeProps } from "@base-ui/react/merge-props"
import { useRender } from "@base-ui/react/use-render"
import { cva, type VariantProps } from "class-variance-authority"

import { cn } from "@/lib/utils"

const badgeVariants = cva(
  "group/badge inline-flex h-5 w-fit shrink-0 items-center justify-center gap-1 overflow-hidden rounded-[4px] border px-2 py-0.5 text-[10px] font-mono font-medium uppercase tracking-[0.06em] whitespace-nowrap transition-all duration-150 [&>svg]:pointer-events-none [&>svg]:size-3!",
  {
    variants: {
      variant: {
        default:
          "border-flow-700 bg-flow-800 text-flow-200",
        amber:
          "border-flow-amber/30 bg-flow-amber/10 text-flow-amber",
        secondary:
          "border-flow-700 bg-flow-800 text-flow-300",
        destructive:
          "border-destructive/30 bg-destructive/10 text-destructive",
        outline:
          "border-flow-700 bg-transparent text-flow-300",
        ghost:
          "border-transparent bg-transparent text-flow-400",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  }
)

function Badge({
  className,
  variant = "default",
  render,
  ...props
}: useRender.ComponentProps<"span"> & VariantProps<typeof badgeVariants>) {
  return useRender({
    defaultTagName: "span",
    props: mergeProps<"span">(
      {
        className: cn(badgeVariants({ variant }), className),
      },
      props
    ),
    render,
    state: {
      slot: "badge",
      variant: variant ?? "default",
    },
  })
}

export { Badge, badgeVariants }
export type BadgeVariant = NonNullable<VariantProps<typeof badgeVariants>["variant"]>
