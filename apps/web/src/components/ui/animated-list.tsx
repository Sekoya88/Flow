'use client'

import React, { Children, cloneElement, isValidElement } from 'react'
import { cn } from '@/lib/utils'

interface AnimatedListProps {
  children: React.ReactNode
  stagger?: number
  className?: string
  /** Animation class — defaults to `animate-slide-up`. */
  animation?: string
}

/**
 * Wraps a list of children, injecting `animate-slide-up` + a staggered
 * `animationDelay` on each so list entrances feel choreographed.
 *
 * The wrapper clones each child to merge into its existing className/style;
 * it does NOT add a wrapping DOM node per item, so existing grid/flex layouts
 * still apply.
 */
export function AnimatedList({
  children,
  stagger = 60,
  className,
  animation = 'animate-slide-up',
}: AnimatedListProps) {
  return (
    <div className={className}>
      {Children.map(children, (child, i) => {
        if (!isValidElement(child)) return child
        const existingClass = (child.props as { className?: string }).className ?? ''
        const existingStyle = (child.props as { style?: React.CSSProperties }).style ?? {}
        return cloneElement(child as React.ReactElement<{ className?: string; style?: React.CSSProperties }>, {
          className: cn(animation, existingClass),
          style: { animationDelay: `${i * stagger}ms`, ...existingStyle },
        })
      })}
    </div>
  )
}
