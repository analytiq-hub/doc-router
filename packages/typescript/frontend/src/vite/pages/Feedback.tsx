import Layout from '@/components/Layout';
import FeedbackForm from '@/components/FeedbackForm';

export function FeedbackPage() {
  return (
    <Layout>
      <div className="container mx-auto px-4 py-8">
        <FeedbackForm />
      </div>
    </Layout>
  );
}
