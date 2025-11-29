import { useState, useEffect } from 'react';
import { useRouter } from 'next/router';
import { proofsAPI } from '@/lib/api';
import { Proof } from '@/types';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar';
import { Textarea } from '@/components/ui/textarea';
import { ArrowLeft, CheckCircle2, XCircle, MessageCircle } from 'lucide-react';
import { toast } from 'sonner';
import { formatDistanceToNow } from 'date-fns';

export default function VerifyProofPage() {
  const router = useRouter();
  const { proofId } = router.query;
  
  const [proof, setProof] = useState<Proof | null>(null);
  const [loading, setLoading] = useState(true);
  const [comment, setComment] = useState('');
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (proofId) {
      loadProof();
    }
  }, [proofId]);

  const loadProof = async () => {
    try {
      const data = await proofsAPI.get(proofId as string);
      setProof(data);
    } catch (error) {
      console.error('Failed to load proof:', error);
      toast.error('Failed to load proof details');
    } finally {
      setLoading(false);
    }
  };

  const handleVerify = async (approved: boolean) => {
    setSubmitting(true);
    try {
      await proofsAPI.verify(proofId as string, approved, comment);
      toast.success(approved ? 'Proof approved!' : 'Proof rejected');
      
      setTimeout(() => {
        router.push('/verification');
      }, 1500);
    } catch (error) {
      console.error('Verification failed:', error);
      toast.error('Verification failed');
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return (
      <div className="max-w-4xl mx-auto p-6">
        <div className="flex items-center justify-center py-12">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
        </div>
      </div>
    );
  }

  if (!proof) {
    return (
      <div className="max-w-4xl mx-auto p-6">
        <Card>
          <CardContent className="py-12 text-center">
            <p className="text-gray-500">Proof not found</p>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto p-6 space-y-6">
      <div className="flex items-center gap-4">
        <Button variant="ghost" onClick={() => router.back()}>
          <ArrowLeft className="h-5 w-5 mr-2" />
          Back
        </Button>
        <div>
          <h1 className="text-3xl font-bold">Verify Proof</h1>
          <p className="text-gray-600">Review and verify your friend's milestone proof</p>
        </div>
      </div>

      <Card>
        <CardHeader>
          <Badge variant="outline" className="mb-2">Goal</Badge>
          <CardTitle>{proof.goalTitle}</CardTitle>
          {proof.milestoneTitle && (
            <CardDescription>
              Milestone: <span className="font-medium">{proof.milestoneTitle}</span>
            </CardDescription>
          )}
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center gap-3">
            <Avatar>
              <AvatarImage 
                src={`https://api.dicebear.com/7.x/avataaars/svg?seed=${proof.userName}`} 
              />
              <AvatarFallback>{proof.userName?.[0] || 'U'}</AvatarFallback>
            </Avatar>
            <div>
              <p className="font-medium">{proof.userName}</p>
              <p className="text-sm text-gray-500">
                Submitted {formatDistanceToNow(new Date(proof.uploadedAt || proof.created_at || new Date()), { addSuffix: true })}
              </p>
            </div>
          </div>

          {proof.image_url && (
            <div className="rounded-lg overflow-hidden border">
              <img 
                src={proof.image_url} 
                alt="Proof"
                className="w-full max-h-[600px] object-contain bg-gray-100"
              />
            </div>
          )}

          {proof.caption && (
            <div className="bg-gray-50 p-4 rounded-lg">
              <p className="text-sm text-gray-900">
                <MessageCircle className="h-4 w-4 inline mr-2" />
                {proof.caption}
              </p>
            </div>
          )}
        </CardContent>
      </Card>

      {proof.verifications.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Previous Verifications</CardTitle>
            <CardDescription>
              {proof.verifications.length} of {proof.requiredVerifications} verifications received
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {proof.verifications.map((verification) => (
              <div key={verification.id} className="flex items-start gap-3 p-3 border rounded-lg">
                <Avatar>
                  <AvatarImage 
                    src={`https://api.dicebear.com/7.x/avataaars/svg?seed=${verification.verifierName}`} 
                  />
                  <AvatarFallback>{verification.verifierName?.[0] || 'V'}</AvatarFallback>
                </Avatar>
                <div className="flex-1">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="font-medium">{verification.verifierName}</span>
                    <Badge variant={verification.approved ? 'default' : 'destructive'} className="text-xs">
                      {verification.approved ? 'Approved' : 'Rejected'}
                    </Badge>
                  </div>
                  <p className="text-xs text-gray-500 mb-2">
                    {formatDistanceToNow(new Date(verification.created_at), { addSuffix: true })}
                  </p>
                  {verification.comment && (
                    <p className="text-sm bg-gray-50 p-2 rounded">{verification.comment}</p>
                  )}
                </div>
              </div>
            ))}
          </CardContent>
        </Card>
      )}

      {proof.status === 'pending' && (
        <Card>
          <CardHeader>
            <CardTitle>Your Verification</CardTitle>
            <CardDescription>Add an optional comment and verify this proof</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <label className="text-sm font-medium">Comment (Optional)</label>
              <Textarea
                placeholder="Add a comment about this proof..."
                value={comment}
                onChange={(e) => setComment(e.target.value)}
                rows={3}
              />
            </div>

            <div className="flex gap-3">
              <Button
                className="flex-1 bg-green-600 hover:bg-green-700"
                onClick={() => handleVerify(true)}
                disabled={submitting}
              >
                {submitting ? (
                  <>
                    <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2"></div>
                    Processing...
                  </>
                ) : (
                  <>
                    <CheckCircle2 className="h-4 w-4 mr-2" />
                    Verify (Approve)
                  </>
                )}
              </Button>
              <Button
                variant="destructive"
                className="flex-1"
                onClick={() => handleVerify(false)}
                disabled={submitting}
              >
                <XCircle className="h-4 w-4 mr-2" />
                Reject
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {proof.status !== 'pending' && (
        <Card>
          <CardContent className="py-6">
            <div className="text-center">
              <Badge 
                variant={proof.status === 'approved' ? 'default' : 'destructive'}
                className="text-lg px-6 py-3"
              >
                {proof.status === 'approved' ? (
                  <CheckCircle2 className="h-5 w-5 mr-2" />
                ) : (
                  <XCircle className="h-5 w-5 mr-2" />
                )}
                This proof has been {proof.status}
              </Badge>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}