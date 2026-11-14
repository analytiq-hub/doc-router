import { mergeProps } from "@base-ui/react/merge-props"
import { useRender } from "@base-ui/react/use-render"
import { cva, type VariantProps } from "class-variance-authority"
import { cn } from "cn"

const badgeVariants = cva(
  "group/badge inline-flex h-5 w-fit shrink-0 items-center justify-center gap-1 overflow-hidden rounded-lg border border-transparent px-2 py-0.5 text-xs font-medium whitespace-nowrap transition-all focus-visible:border-ring focus-visible:ring-[3px] focus-visible:ring-ring has-data-[icon=inline-end]:pr-1.5 has-data-[icon=inline-start]:pl-1.5 aria-invalid:border-destructive aria-invalid:ring-destructive/20 dark:aria-invalid:ring-destructive/40 [&>svg]:pointer-events-none [&>svg]:size-3!",
  {
    variants: {
      variant: {
        default:
          "bg-primary text-primary-foreground [a]:hover:bg-primary/80 group-focus/dropdown-menu-item:text-primary-soft",
        secondary:
          "bg-secondary text-secondary-foreground [a]:hover:bg-secondary/80 group-focus/dropdown-menu-item:border-border group-focus/dropdown-menu-item:bg-card group-focus/dropdown-menu-item:text-muted-foreground",
        // solid for contrast (see button.tsx)
        destructive:
          "bg-destructive text-white focus-visible:ring-destructive [a]:hover:bg-destructive/90",
        outline:
          "border-border text-foreground [a]:hover:bg-muted [a]:hover:text-muted-foreground group-focus/dropdown-menu-item:bg-card group-focus/dropdown-menu-item:text-muted-foreground",
        ghost:
          "hover:bg-muted hover:text-muted-foreground dark:hover:bg-muted/50",
        link: "text-primary underline-offset-4 hover:underline",
        // soft status badges: light background, dark text, a colored border
        info: "border-primary/30 bg-primary-soft text-primary",
        success: "border-success/30 bg-success-soft text-foreground",
        danger: "border-destructive/30 bg-destructive-soft text-destructive",
        warning: "border-warning/30 bg-warning-soft text-warning",
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
      variant,
    },
  })
}

export { Badge, badgeVariants }
