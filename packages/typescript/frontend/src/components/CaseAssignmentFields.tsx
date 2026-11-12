'use client'

import { Checkbox } from '@/components/ui/checkbox'
import { Field, FieldContent, FieldDescription, FieldLabel } from '@/components/ui/field'
import { Input } from '@/components/ui/input'

type CaseAssignmentFieldsProps = {
  caseId: string
  onCaseIdChange: (value: string) => void
  createCaseIfMissing: boolean
  onCreateCaseIfMissingChange: (value: boolean) => void
  disabled?: boolean
}

export function CaseAssignmentFields({
  caseId,
  onCaseIdChange,
  createCaseIfMissing,
  onCreateCaseIfMissingChange,
  disabled = false,
}: CaseAssignmentFieldsProps) {
  return (
    <div className="space-y-4">
      <Field>
        <FieldLabel htmlFor="case-id-input">Case ID</FieldLabel>
        <FieldContent>
          <Input
            id="case-id-input"
            value={caseId}
            onChange={(e) => onCaseIdChange(e.target.value)}
            disabled={disabled}
            placeholder="e.g. CLM-123 (leave empty to skip or clear)"
          />
        </FieldContent>
        <FieldDescription>
          Assign this document to a case. Clear the field and save to remove from a case.
        </FieldDescription>
      </Field>
      <Field orientation="horizontal">
        <Checkbox
          checked={createCaseIfMissing}
          disabled={disabled || !caseId.trim()}
          onCheckedChange={(checked) => onCreateCaseIfMissingChange(checked === true)}
        />
        <FieldLabel className="font-normal">Create case if it does not exist</FieldLabel>
      </Field>
    </div>
  )
}
