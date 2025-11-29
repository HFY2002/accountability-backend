import { useState, useEffect } from 'react';
import { proofsAPI, notificationsAPI } from '../../lib/api';
import { Proof, GoalCompletionRequest } from '../../types';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../ui/card';
import { Button } from '../ui/button';
import { Badge } from '../ui/badge';
import { Avatar, AvatarFallback, AvatarImage } from '../ui/avatar';
import { Textarea } from '../ui/textarea';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../ui/tabs';
import {
  CheckCircle2, 
  XCircle, 
  Clock, 
  MessageCircle,
  ChevronDown,
  ChevronUp,
  Flag,
  Target
} from 'lucide-react';
import { toast } from 'sonner';
import { formatDistanceToNow } from 'date-fns';

export function VerificationQueue() {
  const [proofs, setProofs] = useState<Proof[]>([]);
  const [expandedProof, setExpandedProof] = useState<string | null>(null);
  const [comment, setComment] = useState('');
  const [loading, setLoading] = useState(true);
  const [unreadCount, setUnreadCount] = useState(0);
  
  // Mock goal completion requests
  const [goalCompletionRequests, setGoalCompletionRequests] = useState<GoalCompletionRequest[]>([]);

  const loadUnreadCount = async () => {
    try {
      const data = await notificationsAPI.getUnreadCount();
      setUnreadCount(data?.unread_count || 0);
    } catch (error) {
      console.error("Failed to load notification count:", error);
    }
  };

  const loadProofs = async () => {
    setLoading(true);
    try {
      const data = await proofsAPI.list();
      setProofs(data || []);
    } catch (error: any) {
      console.error('Failed to load verification queue:', error);
      toast.error('Failed to load verification queue');
      setProofs([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadProofs();
    loadUnreadCount();
  }, []);

  // Separate proofs into "My Pending" (submitted by me) and "Friends' Verifications" (submitted by friends)
  const currentUserId = localStorage.getItem('user') ? JSON.parse(localStorage.getItem('user')!).id : '1';
  const myPendingProofs = proofs.filter(p => p.user_id === currentUserId);
  const friendsProofs = proofs.filter(p => p.user_id !== currentUserId && p.status === 'pending');

  const handleVerify = async (proofId: string, approved: boolean) => {
    setLoading(true);
    try {
      await proofsAPI.verify(proofId, approved, comment);
      toast.success(approved ? 'Proof approved!' : 'Proof rejected');
      setComment('');
      setExpandedProof(null);
      await loadProofs();
    } catch (error: any) {
      console.error('Verification failed:', error);
      toast.error('Verification failed');
    } finally {
      setLoading(false);
    }
  };

  const handleVerifyGoalCompletion = (requestId: string, approved: boolean) => {
    setGoalCompletionRequests(prev => prev.map(req =>
      req.id === requestId ? {
        ...req,
        verified: true,
        verifiedBy: 'Alex Johnson',
        verifiedAt: new Date().toISOString(),
      } : req
    ));
    
    const request = goalCompletionRequests.find(r => r.id === requestId);
    if (approved) {
      toast.success(`${request?.user_name}'s goal "${request?.goal_title}" has been verified as complete!`);
    } else {
      toast.error(`${request?.user_name}'s goal completion was rejected`);
    }
  };

  const pendingGoalRequests = goalCompletionRequests.filter(r => !r.verified);
  const totalPendingVerifications = friendsProofs.length + pendingGoalRequests.length;

  const handleProofClick = (proofId: string) => {
    // Navigate to verification detail page
    window.location.href = `/verify/${proofId}`;
  };

  return (
    <div className="space-y-6">
      <div>
        <h2>Verification Queue</h2>
        <p className="text-gray-600">
          Review proof submissions and goal completions
        </p>
      </div>

      <Tabs defaultValue="friends">
        <TabsList>
          <TabsTrigger value="friends" className="gap-2">
            {totalPendingVerifications > 0 && (
              <Badge variant="destructive" className="ml-2">
                {totalPendingVerifications}
              </Badge>
            )}
            <Target className="h-4 w-4" />
            Friends' Verifications ({friendsProofs.length + pendingGoalRequests.length})
          </TabsTrigger>
          <TabsTrigger value="my-pending" className="gap-2">
            {myPendingProofs.length > 0 && (
              <Badge variant="secondary" className="ml-2">
                {myPendingProofs.length}
              </Badge>
            )}
            <Clock className="h-4 w-4" />
            My Pending ({myPendingProofs.length})
          </TabsTrigger>
        </TabsList>

        {/* Friends' Verifications Tab */}
        <TabsContent value="friends" className="space-y-6">
          {/* Milestone Proof Verifications */}
          <div className="space-y-4">
            <div>
              <h3>Milestone Proofs ({friendsProofs.length})</h3>
              <p className="text-sm text-gray-600">Verify your friends' milestone submissions</p>
            </div>
            
            {friendsProofs.length === 0 ? (
              <Card>
                <CardContent className="py-8 text-center text-gray-500">
                  <Clock className="h-12 w-12 mx-auto mb-3 text-gray-400" />
                  <p>No pending verifications from friends</p>
                </CardContent>
              </Card>
            ) : (
              friendsProofs.map((proof) => (
                <Card
                  key={proof.id}
                  className="overflow-hidden cursor-pointer hover:shadow-lg transition-shadow"
                  onClick={() => handleProofClick(proof.id)}
                >
                  <CardHeader>
                    <div className="flex items-start justify-between">
                      <div className="flex items-center gap-3">
                        <Avatar>
                          <AvatarImage src={`https://api.dicebear.com/7.x/avataaars/svg?seed=${proof.userName}`} />
                          <AvatarFallback>{proof.userName?.[0] || 'U'}</AvatarFallback>
                        </Avatar>
                        <div>
                          <CardTitle className="text-lg">{proof.userName}</CardTitle>
                          <CardDescription>
                            {formatDistanceToNow(new Date(proof.uploadedAt || proof.created_at || new Date()), { addSuffix: true })}
                          </CardDescription>
                        </div>
                      </div>
                      <Badge variant="secondary">
                        {proof.verifications.length} / {proof.requiredVerifications} verified
                      </Badge>
                    </div>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    {proof.image_url && (
                      <div className="rounded-lg overflow-hidden">
                        <img 
                          src={proof.image_url} 
                          alt="Proof"
                          className="w-full max-h-48 object-cover"
                        />
                      </div>
                    )}
                    
                    <div>
                      {proof.goalTitle && (
                        <p className="text-sm font-medium text-gray-900">{proof.goalTitle}</p>
                      )}
                      {proof.milestoneTitle && (
                        <p className="text-sm text-gray-600">{proof.milestoneTitle}</p>
                      )}
                      {proof.caption && (
                        <p className="text-sm text-gray-500 mt-2 italic">
                          <MessageCircle className="h-3 w-3 inline mr-1" />
                          {proof.caption}
                        </p>
                      )}
                    </div>
                  </CardContent>
                </Card>
              ))
            )}
          </div>
        </TabsContent>

        {/* My Pending Tab */}
        <TabsContent value="my-pending" className="space-y-6">
          <div className="space-y-4">
            {myPendingProofs.length === 0 ? (
              <Card>
                <CardContent className="py-8 text-centered text-gray-500">
                  <CheckCircle2 className="h-12 w-12 mx-auto mb-3 text-gray-400" />
                  <p>You have no pending proofs</p>
                </CardContent>
              </Card>
            ) : (
              myPendingProofs.map((proof) => (
                <Card key={proof.id} className="overflow-hidden">
                  <CardHeader>
                    <div className="flex items-start justify-between">
                      <div>
                        <CardTitle className="text-lg">{proof.goalTitle}</CardTitle>
                        {proof.milestoneTitle && (
                          <p className="text-sm text-gray-600">{proof.milestoneTitle}</p>
                        )}
                      </div>
                      <Badge variant={proof.status === 'approved' ? 'default' : 'secondary'}>
                        {proof.status}
                      </Badge>
                    </div>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <div className="flex items-center justify-between text-sm">
                      <span className="text-gray-600">
                        {proof.verifications.length} / {proof.requiredVerifications} approvals
                      </span>
                      <span className="text-gray-500">
                        {formatDistanceToNow(new Date(proof.uploadedAt || proof.created_at || new Date()), { addSuffix: true })}
                      </span>
                    </div>
                    
                    {proof.verifications.length > 0 && (
                      <div className="space-y-2">
                        <p className="text-sm font-medium text-gray-900">Verifications:</p>
                        {proof.verifications.map((v) => (
                          <div key={v.id} className="flex items-center gap-2 text-sm">
                            {v.approved ? (
                              <CheckCircle2 className="h-4 w-4 text-green-600" />
                            ) : (
                              <XCircle className="h-4 w-4 text-red-600" />
                            )}
                            <span className="text-gray-600">{v.verifierName}</span>
                            {v.comment && (
                              <span className="text-gray-500 italic">"{v.comment}"</span>
                            )}
                          </div>
                        ))}
                      </div>
                    )}
                  </CardContent>
                </Card>
              ))
            )}
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
}