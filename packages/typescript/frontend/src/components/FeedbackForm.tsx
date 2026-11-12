'use client'

import React, { useState } from 'react'
import { Link } from 'react-router-dom'
import { MessageSquare, Shield } from 'lucide-react'
import { useAppSession } from '@/contexts/AppSessionContext'
import { isSysAdmin } from '@/utils/roles'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Field, FieldLabel } from '@/components/ui/field'
import { Textarea } from '@/components/ui/textarea'

interface FeedbackFormProps {
  onClose?: () => void
  isModal?: boolean
}

const FeedbackForm: React.FC<FeedbackFormProps> = ({ onClose, isModal = false }) => {
  const { session } = useAppSession()
  const [feedback, setFeedback] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [submitStatus, setSubmitStatus] = useState<'idle' | 'success' | 'error'>('idle')
  const [errorMessage, setErrorMessage] = useState('')

  const isAdmin = isSysAdmin(session)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()

    if (!feedback.trim()) {
      setSubmitStatus('error')
      setErrorMessage('Please provide feedback before submitting.')
      return
    }

    setIsSubmitting(true)
    setSubmitStatus('idle')

    try {
      const response = await fetch('/fastapi/v0/feedback', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        credentials: 'include',
        body: JSON.stringify({
          feedback,
          userId: session?.user?.id,
          userName: session?.user?.name,
          createdAt: new Date().toISOString(),
        }),
      })

      if (!response.ok) {
        throw new Error('Failed to submit feedback')
      }

      setSubmitStatus('success')
      setFeedback('')

      if (isModal && onClose) {
        setTimeout(() => {
          onClose()
        }, 2000)
      }
    } catch (submitError) {
      console.error('Error submitting feedback:', submitError)
      setSubmitStatus('error')
      setErrorMessage('Failed to submit feedback. Please try again later.')
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <Card className={isModal ? undefined : 'mx-auto my-8 max-w-2xl'}>
      <CardHeader className="flex flex-row flex-wrap items-center justify-between gap-3 space-y-0">
        <CardTitle className="flex items-center gap-2 text-xl">
          <MessageSquare className="size-5 text-primary" />
          Product feedback
        </CardTitle>

        {isAdmin ? (
          <Button variant="link" size="sm" className="h-auto px-0" render={<Link to="/admin/feedback" />}>
            <Shield className="size-4" />
            View all feedback
          </Button>
        ) : null}
      </CardHeader>

      <CardContent>
        <p className="mb-6 text-sm text-muted-foreground">
          We value your feedback. Use this form to report bugs, share suggestions, or send kudos.
        </p>

        <form onSubmit={(e) => void handleSubmit(e)} className="space-y-4">
          <Field>
            <FieldLabel htmlFor="feedback">
              Your feedback <span className="text-destructive">*</span>
            </FieldLabel>
            <Textarea
              id="feedback"
              rows={5}
              placeholder="Describe your issue, suggestion, or appreciation here…"
              value={feedback}
              onChange={(e) => setFeedback(e.target.value)}
              required
            />
          </Field>

          {session?.user?.email ? (
            <p className="text-sm text-muted-foreground">
              Feedback will be submitted using your account email: {session.user.email}
            </p>
          ) : null}

          {submitStatus === 'success' ? (
            <Alert variant="success">
              <AlertDescription>Thank you for your feedback. We appreciate your input.</AlertDescription>
            </Alert>
          ) : null}

          {submitStatus === 'error' ? (
            <Alert variant="destructive">
              <AlertDescription>{errorMessage}</AlertDescription>
            </Alert>
          ) : null}

          <Button type="submit" className="w-full" disabled={isSubmitting}>
            {isSubmitting ? 'Submitting…' : 'Submit feedback'}
          </Button>
        </form>
      </CardContent>
    </Card>
  )
}

export default FeedbackForm
