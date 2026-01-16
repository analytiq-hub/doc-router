import { Fragment, useState } from 'react'
import { Dialog, Transition } from '@headlessui/react'
import { XMarkIcon, PlusIcon, TrashIcon } from '@heroicons/react/24/outline'
import { Tag } from '@docrouter/sdk';
import TagSelector from './TagSelector';

interface DocumentUpdateProps {
  isOpen: boolean
  onClose: () => void
  documentName: string
  currentTags: string[]
  currentMetadata?: Record<string, string>
  availableTags: Tag[]
  onSave: (tagIds: string[], metadata: Record<string, string>) => Promise<void>
}

export function DocumentUpdate({ 
  isOpen, 
  onClose, 
  documentName, 
  currentTags, 
  currentMetadata = {},
  availableTags,
  onSave 
}: DocumentUpdateProps) {
  const [selectedTags, setSelectedTags] = useState(currentTags)
  const [metadataFields, setMetadataFields] = useState<Array<{id: string, key: string, value: string}>>(
    Object.entries(currentMetadata).map(([key, value], index) => ({
      id: `field_${index}`,
      key,
      value
    }))
  )
  const [validationError, setValidationError] = useState<string | null>(null)

  const handleAddMetadata = () => {
    const newId = `field_${Date.now()}`
    setMetadataFields(prev => [...prev, { id: newId, key: '', value: '' }])
  }

  const handleRemoveMetadata = (id: string) => {
    setMetadataFields(prev => prev.filter(field => field.id !== id))
  }

  const handleMetadataKeyChange = (id: string, newKey: string) => {
    setMetadataFields(prev => 
      prev.map(field => 
        field.id === id ? { ...field, key: newKey } : field
      )
    )
    // Clear validation error when user makes changes
    setValidationError(null)
  }

  const handleMetadataValueChange = (id: string, newValue: string) => {
    setMetadataFields(prev => 
      prev.map(field => 
        field.id === id ? { ...field, value: newValue } : field
      )
    )
    // Clear validation error when user makes changes
    setValidationError(null)
  }

  const handleSave = async () => {
    // Filter out empty keys and convert to object
    const nonEmptyFields = metadataFields.filter(field => field.key.trim() !== '')
    const cleanMetadata: Record<string, string> = {}
    
    // Check for duplicate keys
    const keys = nonEmptyFields.map(field => field.key)
    const duplicateKeys = keys.filter((key, index) => keys.indexOf(key) !== index)
    
    if (duplicateKeys.length > 0) {
      setValidationError(`Duplicate keys found: ${duplicateKeys.join(', ')}. Please remove or rename duplicate keys.`)
      return
    }
    
    // Convert to object
    nonEmptyFields.forEach(field => {
      cleanMetadata[field.key] = field.value
    })
    
    await onSave(selectedTags, cleanMetadata);
    onClose();
  };

  return (
    <Transition show={isOpen} as={Fragment}>
      <Dialog as="div" className="relative z-50" onClose={onClose}>
        <div className="fixed inset-0 bg-gray-500 bg-opacity-75 transition-opacity" />

        <div className="fixed inset-0 overflow-hidden">
          <div className="absolute inset-0 overflow-hidden">
            <div className="pointer-events-none fixed inset-y-0 right-0 flex max-w-full pl-10">
              <div className="pointer-events-auto w-screen max-w-md">
                <div className="flex h-full flex-col bg-white shadow-xl">
                  <div className="px-4 py-6 sm:px-6">
                    <div className="flex items-start justify-between">
                      <h2 className="text-base font-semibold leading-6 text-gray-900">
                        Update Document: {documentName}
                      </h2>
                      <button
                        type="button"
                        className="rounded-md text-gray-400 hover:text-gray-500"
                        onClick={onClose}
                      >
                        <XMarkIcon className="h-6 w-6" />
                      </button>
                    </div>
                    <span className="text-sm text-gray-500">Click on tags to enable or disable them</span>
                  </div>
                  <div className="flex-1 overflow-y-auto px-4 sm:px-6 space-y-6">
                    {/* Tags Section */}
                    <div>
                      <h3 className="text-sm font-medium text-gray-900 mb-3">Tags</h3>
                      <TagSelector
                        availableTags={availableTags}
                        selectedTagIds={selectedTags}
                        onChange={setSelectedTags}
                      />
                    </div>

                    {/* Metadata Section */}
                    <div>
                      <div className="flex items-center justify-between mb-3">
                        <h3 className="text-sm font-medium text-gray-900">Metadata</h3>
                        <button
                          type="button"
                          onClick={handleAddMetadata}
                          className="inline-flex items-center px-2 py-1 text-xs font-medium text-blue-600 hover:text-blue-500"
                        >
                          <PlusIcon className="h-4 w-4 mr-1" />
                          Add Field
                        </button>
                      </div>
                      
                      <div className="space-y-2">
                        {metadataFields.map((field) => (
                          <div key={field.id} className="flex gap-2 items-center">
                            <input
                              type="text"
                              placeholder="Key"
                              value={field.key}
                              onChange={(e) => handleMetadataKeyChange(field.id, e.target.value)}
                              className="flex-1 rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 text-sm"
                            />
                            <input
                              type="text"
                              placeholder="Value"
                              value={field.value}
                              onChange={(e) => handleMetadataValueChange(field.id, e.target.value)}
                              className="flex-1 rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 text-sm"
                            />
                            <button
                              type="button"
                              onClick={() => handleRemoveMetadata(field.id)}
                              className="text-red-500 hover:text-red-700"
                            >
                              <TrashIcon className="h-4 w-4" />
                            </button>
                          </div>
                        ))}
                        {metadataFields.length === 0 && (
                          <p className="text-sm text-gray-500 italic">No metadata fields. Click &quot;Add Field&quot; to add some.</p>
                        )}
                      </div>
                      
                      {/* Validation Error Display */}
                      {validationError && (
                        <div className="mt-3 p-3 bg-red-50 border border-red-200 rounded-md">
                          <p className="text-sm text-red-600">{validationError}</p>
                        </div>
                      )}
                    </div>
                  </div>
                  <div className="flex flex-shrink-0 justify-end gap-3 px-4 py-4">
                    <button
                      type="button"
                      className="rounded-md bg-white px-3 py-2 text-sm font-semibold text-gray-900 shadow-sm ring-1 ring-inset ring-gray-300 hover:bg-gray-50"
                      onClick={onClose}
                    >
                      Cancel
                    </button>
                    <button
                      type="button"
                      className="rounded-md bg-blue-600 px-3 py-2 text-sm font-semibold text-white shadow-sm hover:bg-blue-500"
                      onClick={handleSave}
                    >
                      Save
                    </button>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </Dialog>
    </Transition>
  )
} 