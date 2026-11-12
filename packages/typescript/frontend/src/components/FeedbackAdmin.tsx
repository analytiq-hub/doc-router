'use client'

import React, { useEffect, useState } from 'react'
import { Trash2 } from 'lucide-react'
import { formatLocalDate } from '@/utils/date'
import { ConfirmDialog } from '@/components/ConfirmDialog'
import { SearchInput } from '@/components/SearchInput'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'

interface FeedbackItem {
  _id: string
  content: string
  email: string
  userName: string | null
  createdAt: string
  status: string
}

const FeedbackAdmin: React.FC = () => {
  const [feedback, setFeedback] = useState<FeedbackItem[]>([])
  const [filteredFeedback, setFilteredFeedback] = useState<FeedbackItem[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [searchEmail, setSearchEmail] = useState('')

  const [currentPage, setCurrentPage] = useState(1)
  const itemsPerPage = 5
  const [totalPages, setTotalPages] = useState(1)

  const [deleteId, setDeleteId] = useState<string | null>(null)
  const [isDeleting, setIsDeleting] = useState(false)

  useEffect(() => {
    void fetchFeedback()
  }, [])

  useEffect(() => {
    const filtered = feedback.filter(
      (item) => !searchEmail || item.email.toLowerCase().includes(searchEmail.toLowerCase()),
    )

    setFilteredFeedback(filtered)
    setTotalPages(Math.max(1, Math.ceil(filtered.length / itemsPerPage)))
    setCurrentPage(1)
  }, [feedback, searchEmail])

  const fetchFeedback = async () => {
    setIsLoading(true)
    try {
      const response = await fetch('/fastapi/v0/admin/feedback', { credentials: 'include' })

      if (!response.ok) {
        throw new Error('Failed to fetch feedback')
      }

      const data = await response.json()
      setFeedback(data.feedback)
      setFilteredFeedback(data.feedback)
      setTotalPages(Math.max(1, Math.ceil(data.feedback.length / itemsPerPage)))
    } catch (err) {
      setError('Error loading feedback. Please try again later.')
      console.error('Error fetching feedback:', err)
    } finally {
      setIsLoading(false)
    }
  }

  const confirmDelete = async () => {
    if (!deleteId) return

    setIsDeleting(true)
    try {
      const response = await fetch(`/fastapi/v0/admin/feedback/${deleteId}`, {
        method: 'DELETE',
        credentials: 'include',
      })

      if (!response.ok) {
        throw new Error('Failed to delete feedback')
      }

      setFeedback(feedback.filter((item) => item._id !== deleteId))
      setDeleteId(null)
    } catch (err) {
      setError('Error deleting feedback. Please try again later.')
      console.error('Error deleting feedback:', err)
    } finally {
      setIsDeleting(false)
    }
  }

  const handlePageChange = (page: number) => {
    setCurrentPage(page)
  }

  const getCurrentItems = () => {
    const startIndex = (currentPage - 1) * itemsPerPage
    const endIndex = startIndex + itemsPerPage
    return filteredFeedback.slice(startIndex, endIndex)
  }

  if (isLoading) {
    return <p className="py-8 text-center text-sm text-muted-foreground">Loading feedback…</p>
  }

  if (error) {
    return (
      <Alert variant="destructive" className="my-4">
        <AlertDescription>{error}</AlertDescription>
      </Alert>
    )
  }

  if (feedback.length === 0) {
    return <p className="py-8 text-center text-sm text-muted-foreground">No feedback submissions yet.</p>
  }

  return (
    <div className="space-y-6">
      <Card>
        <CardContent className="flex flex-col items-center gap-4 pt-6 sm:flex-row">
          <SearchInput
            className="w-full flex-grow"
            placeholder="Search by email…"
            value={searchEmail}
            onChange={setSearchEmail}
          />
          <p className="text-sm text-muted-foreground whitespace-nowrap">
            Showing {filteredFeedback.length} results
          </p>
        </CardContent>
      </Card>

      {getCurrentItems().map((item) => (
        <Card key={item._id}>
          <CardContent className="space-y-4 pt-6">
            <div className="flex items-start justify-between gap-3">
              <div>
                <h3 className="font-medium text-foreground">{item.userName || 'Anonymous user'}</h3>
                <p className="text-sm text-muted-foreground">{item.email}</p>
              </div>
              <div className="flex items-center gap-3">
                <span className="text-sm text-muted-foreground">{formatLocalDate(item.createdAt)}</span>
                <Button
                  type="button"
                  variant="ghost"
                  size="icon-sm"
                  aria-label="Delete feedback"
                  onClick={() => setDeleteId(item._id)}
                >
                  <Trash2 className="text-destructive" />
                </Button>
              </div>
            </div>

            <p className="whitespace-pre-wrap text-foreground">{item.content}</p>

            <div className="flex border-t border-border pt-4">
              <span
                className={`rounded-full px-2 py-1 text-xs ${
                  item.status === 'new'
                    ? 'bg-primary/10 text-primary'
                    : item.status === 'reviewed'
                      ? 'bg-success-soft text-success'
                      : 'bg-muted text-muted-foreground'
                }`}
              >
                {item.status}
              </span>
            </div>
          </CardContent>
        </Card>
      ))}

      {totalPages > 1 ? (
        <nav className="mt-6 flex justify-center">
          <div className="flex items-center gap-1">
            <Button
              type="button"
              variant="secondary"
              size="sm"
              onClick={() => handlePageChange(currentPage - 1)}
              disabled={currentPage === 1}
            >
              Previous
            </Button>

            {Array.from({ length: totalPages }, (_, i) => i + 1).map((page) => (
              <Button
                key={page}
                type="button"
                size="sm"
                variant={currentPage === page ? 'default' : 'secondary'}
                onClick={() => handlePageChange(page)}
              >
                {page}
              </Button>
            ))}

            <Button
              type="button"
              variant="secondary"
              size="sm"
              onClick={() => handlePageChange(currentPage + 1)}
              disabled={currentPage === totalPages}
            >
              Next
            </Button>
          </div>
        </nav>
      ) : null}

      <ConfirmDialog
        open={Boolean(deleteId)}
        title="Confirm deletion"
        message="Are you sure you want to delete this feedback? This action cannot be undone."
        confirmLabel={isDeleting ? 'Deleting…' : 'Delete'}
        busy={isDeleting}
        onConfirm={() => void confirmDelete()}
        onClose={() => setDeleteId(null)}
      />
    </div>
  )
}

export default FeedbackAdmin
