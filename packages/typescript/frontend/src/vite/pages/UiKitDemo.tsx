import { useState } from 'react';
import { toast } from 'sonner';

import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog';
import {
  Field,
  FieldDescription,
  FieldGroup,
  FieldLabel,
} from '@/components/ui/field';
import { Input } from '@/components/ui/input';
import { Separator } from '@/components/ui/separator';
import { Spinner } from '@/components/ui/spinner';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';

export function UiKitDemoPage() {
  const [name, setName] = useState('');

  return (
    <div className="min-h-screen bg-background p-8">
      <div className="mx-auto flex max-w-2xl flex-col gap-6">
        <div>
          <h1 className="text-2xl font-semibold text-foreground">UI kit (shadcn)</h1>
          <p className="text-sm text-muted-foreground">
            Phase 2 smoke page — tokens + core primitives.
          </p>
        </div>

        <Card>
          <CardHeader>
            <CardTitle>Actions</CardTitle>
            <CardDescription>Buttons, badge, spinner, sonner toast.</CardDescription>
          </CardHeader>
          <CardContent className="flex flex-wrap items-center gap-3">
            <Button type="button" onClick={() => toast.success('Saved with sonner')}>
              Toast
            </Button>
            <Button type="button" variant="outline">
              Outline
            </Button>
            <Button type="button" variant="secondary">
              Secondary
            </Button>
            <Badge variant="secondary">Badge</Badge>
            <Spinner className="text-primary" />
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Field + input</CardTitle>
          </CardHeader>
          <CardContent>
            <FieldGroup>
              <Field>
                <FieldLabel htmlFor="demo-name">Name</FieldLabel>
                <Input
                  id="demo-name"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="Type here"
                />
                <FieldDescription>Uses design tokens on focus ring and borders.</FieldDescription>
              </Field>
            </FieldGroup>
          </CardContent>
          <CardFooter className="text-sm text-muted-foreground">
            Value: {name || '—'}
          </CardFooter>
        </Card>

        <Alert>
          <AlertTitle>Heads up</AlertTitle>
          <AlertDescription>
            Alert variants map to <code className="text-xs">--destructive</code> and status tokens.
          </AlertDescription>
        </Alert>

        <Tabs defaultValue="one">
          <TabsList>
            <TabsTrigger value="one">Tab one</TabsTrigger>
            <TabsTrigger value="two">Tab two</TabsTrigger>
          </TabsList>
          <TabsContent value="one" className="text-sm text-muted-foreground">
            First panel
          </TabsContent>
          <TabsContent value="two" className="text-sm text-muted-foreground">
            Second panel
          </TabsContent>
        </Tabs>

        <Separator />

        <Dialog>
          <DialogTrigger render={<Button type="button" variant="outline" />}>
            Open dialog
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Example dialog</DialogTitle>
              <DialogDescription>
                Dialog chrome uses popover tokens and focus trap from Base UI.
              </DialogDescription>
            </DialogHeader>
            <DialogFooter>
              <Button type="button">Confirm</Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>
    </div>
  );
}
