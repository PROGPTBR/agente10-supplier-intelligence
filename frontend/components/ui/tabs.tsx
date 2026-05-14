"use client";

import { Tabs as BaseTabs } from "@base-ui/react/tabs";
import * as React from "react";

/**
 * Lightweight wrapper around @base-ui/react/tabs. Styling is intentionally
 * theme-agnostic — see `.report-page` in globals.css for the editorial look.
 */

export const Tabs = React.forwardRef<
  React.ElementRef<typeof BaseTabs.Root>,
  React.ComponentPropsWithoutRef<typeof BaseTabs.Root>
>(({ className, ...props }, ref) => (
  <BaseTabs.Root ref={ref} className={className} {...props} />
));
Tabs.displayName = "Tabs";

export const TabsList = React.forwardRef<
  React.ElementRef<typeof BaseTabs.List>,
  React.ComponentPropsWithoutRef<typeof BaseTabs.List>
>(({ className, children, ...props }, ref) => (
  <BaseTabs.List
    ref={ref}
    className={`relative inline-flex items-end gap-6 border-b r-rule ${
      className ?? ""
    }`}
    {...props}
  >
    {children}
    <BaseTabs.Indicator
      className="absolute -bottom-px h-0.5 transition-[width,transform] duration-300"
      style={{
        width: "var(--active-tab-width)",
        transform: "translateX(var(--active-tab-left))",
        backgroundColor: "var(--r-accent)",
        transitionTimingFunction: "cubic-bezier(.34,1.56,.64,1)",
      }}
    />
  </BaseTabs.List>
));
TabsList.displayName = "TabsList";

export const TabsTrigger = React.forwardRef<
  React.ElementRef<typeof BaseTabs.Tab>,
  React.ComponentPropsWithoutRef<typeof BaseTabs.Tab>
>(({ className, ...props }, ref) => (
  <BaseTabs.Tab
    ref={ref}
    className={`pb-3 text-sm font-medium text-[var(--r-ink-2)] data-[selected]:text-[var(--r-ink)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--r-accent)] focus-visible:ring-offset-2 focus-visible:ring-offset-[var(--r-bg)] ${
      className ?? ""
    }`}
    {...props}
  />
));
TabsTrigger.displayName = "TabsTrigger";

export const TabsContent = React.forwardRef<
  React.ElementRef<typeof BaseTabs.Panel>,
  React.ComponentPropsWithoutRef<typeof BaseTabs.Panel>
>(({ className, ...props }, ref) => (
  <BaseTabs.Panel
    ref={ref}
    className={`mt-6 focus-visible:outline-none ${className ?? ""}`}
    {...props}
  />
));
TabsContent.displayName = "TabsContent";
