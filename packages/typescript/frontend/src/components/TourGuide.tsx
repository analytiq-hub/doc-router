'use client'

import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react'
import { createPortal } from 'react-dom'

import { useAppSession } from '@/contexts/AppSessionContext'
import { useOrganization } from '@/contexts/OrganizationContext'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import { usePathname, useRouter } from '@/utils/appRouter'
import { hasSeenTour, setHasSeenTour } from '@/utils/tourGuide'

type Placement = 'top' | 'right' | 'bottom' | 'left'

interface TourStep {
  id: string
  title: string
  content: string
  selector: string
  /** Preferred side; falls back to another side when the panel does not fit. */
  placement: Placement
  page?: string
}

declare global {
  interface Window {
    startTourGuide?: () => void
  }
}

type Layout = {
  top: number
  left: number
  placement: Placement
  /** Arrow offset along the panel edge facing the target, in px. */
  arrowOffset: number
}

const GAP = 14
const MARGIN = 12
const ARROW_SIZE = 12

function findTourTarget(selector: string): Element | null {
  const el = document.querySelector(selector)
  if (!el) return null
  const rect = el.getBoundingClientRect()
  if (rect.width <= 0 || rect.height <= 0) return null
  const style = window.getComputedStyle(el)
  if (style.display === 'none' || style.visibility === 'hidden') return null
  return el
}

function fits(placement: Placement, target: DOMRect, w: number, h: number): boolean {
  const vw = window.innerWidth
  const vh = window.innerHeight
  switch (placement) {
    case 'bottom':
      return target.bottom + GAP + h <= vh - MARGIN
    case 'top':
      return target.top - GAP - h >= MARGIN
    case 'right':
      return target.right + GAP + w <= vw - MARGIN
    case 'left':
      return target.left - GAP - w >= MARGIN
  }
}

const FALLBACKS: Record<Placement, Placement[]> = {
  bottom: ['bottom', 'top', 'right', 'left'],
  top: ['top', 'bottom', 'right', 'left'],
  right: ['right', 'bottom', 'left', 'top'],
  left: ['left', 'bottom', 'right', 'top'],
}

function clamp(value: number, min: number, max: number): number {
  return Math.min(Math.max(value, min), Math.max(min, max))
}

function computeLayout(target: DOMRect, w: number, h: number, preferred: Placement): Layout {
  const vw = window.innerWidth
  const vh = window.innerHeight
  const placement = FALLBACKS[preferred].find((p) => fits(p, target, w, h)) ?? 'bottom'
  const centerX = target.left + target.width / 2
  const centerY = target.top + target.height / 2

  let top: number
  let left: number
  if (placement === 'bottom' || placement === 'top') {
    left = clamp(centerX - w / 2, MARGIN, vw - w - MARGIN)
    top = placement === 'bottom' ? target.bottom + GAP : target.top - GAP - h
    top = clamp(top, MARGIN, vh - h - MARGIN)
    const arrowOffset = clamp(centerX - left, ARROW_SIZE + 4, w - ARROW_SIZE - 4)
    return { top, left, placement, arrowOffset }
  }
  top = clamp(centerY - h / 2, MARGIN, vh - h - MARGIN)
  left = placement === 'right' ? target.right + GAP : target.left - GAP - w
  left = clamp(left, MARGIN, vw - w - MARGIN)
  const arrowOffset = clamp(centerY - top, ARROW_SIZE + 4, h - ARROW_SIZE - 4)
  return { top, left, placement, arrowOffset }
}

function arrowStyle(layout: Layout): React.CSSProperties {
  const half = ARROW_SIZE / 2
  switch (layout.placement) {
    case 'bottom':
      return { top: -half, left: layout.arrowOffset - half }
    case 'top':
      return { bottom: -half, left: layout.arrowOffset - half }
    case 'right':
      return { left: -half, top: layout.arrowOffset - half }
    case 'left':
      return { right: -half, top: layout.arrowOffset - half }
  }
}

const ARROW_BORDERS: Record<Placement, string> = {
  bottom: 'border-t border-l',
  top: 'border-b border-r',
  right: 'border-b border-l',
  left: 'border-t border-r',
}

const TourGuide = () => {
  const [currentStep, setCurrentStep] = useState(0)
  const [showTour, setShowTour] = useState(false)
  const [target, setTarget] = useState<Element | null>(null)
  const [layout, setLayout] = useState<Layout | null>(null)
  const [portalHost, setPortalHost] = useState<HTMLElement | null>(null)
  const panelRef = useRef<HTMLDivElement>(null)
  const { session } = useAppSession()
  const router = useRouter()
  const pathname = usePathname()
  const { currentOrganization } = useOrganization()

  const orgIdForTour =
    (pathname.match(/^\/orgs\/([^/]+)/)?.[1] as string | undefined) ?? currentOrganization?.id ?? null

  const tourSteps = useMemo<TourStep[]>(() => {
    if (!orgIdForTour) return []
    const org = orgIdForTour
    return [
      {
        id: 'schemas',
        title: 'Create Schemas',
        content: 'Define document schemas to extract structured data from your documents.',
        selector: '[data-tour="schema-create"]',
        placement: 'bottom',
        page: `/orgs/${org}/schemas`,
      },
      {
        id: 'prompts',
        title: 'Create Prompts',
        content: 'Create and manage prompts to guide AI in processing your documents.',
        selector: '[data-tour="prompt-create"]',
        placement: 'bottom',
        page: `/orgs/${org}/prompts`,
      },
      {
        id: 'upload',
        title: 'Upload Docs',
        content: 'Upload your documents for processing.',
        selector: '[data-tour="upload-documents"]',
        placement: 'bottom',
        page: `/orgs/${org}/docs?tab=upload`,
      },
      {
        id: 'documents',
        title: 'Documents',
        content: 'Click on a document to view the extracted data.',
        selector: '[data-tour="documents"]',
        placement: 'bottom',
        page: `/orgs/${org}/docs?tab=documents`,
      },
      {
        id: 'tags',
        title: 'Configure Tags',
        content: 'With tags, you can determine which prompts are used for which documents.',
        selector: '[data-tour="tag-create"]',
        placement: 'bottom',
        page: `/orgs/${org}/tags`,
      },
      {
        id: 'flows',
        title: 'Flows',
        content:
          'Build visual workflows to automate document processing—connect triggers, AI steps, and integrations in the flow editor.',
        selector: '[data-tour="flows-tab"]',
        placement: 'bottom',
        page: `/orgs/${org}/flows?tab=flows`,
      },
    ]
  }, [orgIdForTour])

  useEffect(() => {
    setPortalHost(document.body)
  }, [])

  const closeTour = useCallback(
    (markSeen: boolean) => {
      setShowTour(false)
      setTarget(null)
      setLayout(null)
      if (markSeen && session) {
        void setHasSeenTour(true, session)
      }
    },
    [session],
  )

  const startTour = useCallback(() => {
    setCurrentStep(0)
    setShowTour(true)
    if (session) {
      void setHasSeenTour(false, session)
    }
  }, [session])

  useEffect(() => {
    let timeoutId: ReturnType<typeof setTimeout>
    const checkTourStatus = async () => {
      if (!session || !orgIdForTour) return
      const seen = await hasSeenTour(session)
      if (!seen) {
        timeoutId = setTimeout(() => setShowTour(true), 1000)
      }
    }
    void checkTourStatus()
    return () => {
      if (timeoutId) clearTimeout(timeoutId)
    }
  }, [session, orgIdForTour])

  useEffect(() => {
    if (!showTour || currentStep >= tourSteps.length) return
    const step = tourSteps[currentStep]
    if (step.page) {
      router.push(step.page)
    }
  }, [showTour, currentStep, tourSteps, router])

  // Wait until the step's element exists and its position has settled before showing the panel.
  useEffect(() => {
    if (!showTour || currentStep >= tourSteps.length) return
    const step = tourSteps[currentStep]
    setTarget(null)
    setLayout(null)

    let cancelled = false
    let attempt = 0
    let lastKey = ''
    let timer: ReturnType<typeof setTimeout>

    const poll = () => {
      if (cancelled) return
      const el = findTourTarget(step.selector)
      if (el) {
        const r = el.getBoundingClientRect()
        const key = `${Math.round(r.top)}:${Math.round(r.left)}:${Math.round(r.width)}:${Math.round(r.height)}`
        if (key === lastKey) {
          el.scrollIntoView({ block: 'nearest', inline: 'nearest' })
          setTarget(el)
          return
        }
        lastKey = key
      } else {
        lastKey = ''
      }
      attempt += 1
      if (attempt >= 60) {
        if (currentStep < tourSteps.length - 1) {
          setCurrentStep((s) => s + 1)
        } else {
          closeTour(true)
        }
        return
      }
      timer = setTimeout(poll, 100)
    }

    timer = setTimeout(poll, 150)
    return () => {
      cancelled = true
      clearTimeout(timer)
    }
  }, [showTour, currentStep, tourSteps, closeTour])

  const reposition = useCallback(() => {
    const panel = panelRef.current
    if (!target || !panel || !target.isConnected) return
    const step = tourSteps[currentStep]
    if (!step) return
    setLayout(
      computeLayout(target.getBoundingClientRect(), panel.offsetWidth, panel.offsetHeight, step.placement),
    )
  }, [target, tourSteps, currentStep])

  // Measure the hidden panel and place it before paint so it appears once, already in position.
  useLayoutEffect(() => {
    reposition()
  }, [reposition])

  useEffect(() => {
    if (!target) return
    window.addEventListener('resize', reposition)
    window.addEventListener('scroll', reposition, true)
    return () => {
      window.removeEventListener('resize', reposition)
      window.removeEventListener('scroll', reposition, true)
    }
  }, [target, reposition])

  useEffect(() => {
    window.startTourGuide = startTour
    return () => {
      delete window.startTourGuide
    }
  }, [startTour])

  const nextStep = () => {
    if (currentStep < tourSteps.length - 1) {
      setCurrentStep((s) => s + 1)
    } else {
      closeTour(true)
    }
  }

  const prevStep = () => {
    if (currentStep > 0) setCurrentStep((s) => s - 1)
  }

  if (!showTour || tourSteps.length === 0 || !portalHost) return null

  const step = tourSteps[currentStep]

  return createPortal(
    <div className="fixed inset-0 z-[300]">
      <button
        type="button"
        className="absolute inset-0 cursor-default bg-black/40"
        aria-label="Dismiss tour"
        onClick={() => closeTour(false)}
      />
      {target ? (
        <div
          ref={panelRef}
          role="dialog"
          aria-label={step.title}
          className={cn(
            'fixed w-[min(calc(100vw-2rem),20rem)] rounded-xl border border-border bg-popover text-popover-foreground shadow-2xl',
            !layout && 'invisible',
          )}
          style={layout ? { top: layout.top, left: layout.left } : { top: 0, left: 0 }}
        >
          {layout ? (
            <div
              aria-hidden
              className={cn(
                'absolute size-3 rotate-45 border-border bg-popover',
                ARROW_BORDERS[layout.placement],
              )}
              style={arrowStyle(layout)}
            />
          ) : null}
          <div className="relative flex flex-col gap-2 p-4">
            <div className="flex items-baseline justify-between gap-2">
              <h3 className="text-base font-semibold">{step.title}</h3>
              <span className="text-xs text-muted-foreground">
                {currentStep + 1}/{tourSteps.length}
              </span>
            </div>
            <p className="text-sm text-muted-foreground">{step.content}</p>
          </div>
          <div className="relative flex items-center justify-between gap-2 border-t border-border px-4 py-3">
            <div>
              {currentStep > 0 ? (
                <Button type="button" variant="outline" size="sm" onClick={prevStep}>
                  Previous
                </Button>
              ) : null}
            </div>
            <div className="flex items-center gap-2">
              <Button type="button" variant="ghost" size="sm" onClick={() => closeTour(true)}>
                Skip tour
              </Button>
              <Button type="button" size="sm" onClick={nextStep}>
                {currentStep < tourSteps.length - 1 ? 'Next' : 'Finish'}
              </Button>
            </div>
          </div>
        </div>
      ) : null}
    </div>,
    portalHost,
  )
}

export default TourGuide
