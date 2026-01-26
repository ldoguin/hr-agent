/**
 * React hooks for the HR Agent API
 *
 * These hooks integrate with TanStack Query for efficient data fetching,
 * caching, and state management.
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { hrAgentClient, type JobMatchResponse, type Candidate } from '@/api/hrAgentClient';
import { toast } from 'sonner';

// Query keys
export const hrAgentKeys = {
  all: ['hrAgent'] as const,
  health: () => [...hrAgentKeys.all, 'health'] as const,
  candidates: () => [...hrAgentKeys.all, 'candidates'] as const,
  candidatesList: (limit: number, offset: number) =>
    [...hrAgentKeys.candidates(), 'list', limit, offset] as const,
  stats: () => [...hrAgentKeys.all, 'stats'] as const,
};

/**
 * Hook to check API health status
 */
export function useHealthCheck() {
  return useQuery({
    queryKey: hrAgentKeys.health(),
    queryFn: () => hrAgentClient.checkHealth(),
    refetchInterval: 30000, // Refetch every 30 seconds
    retry: 3,
  });
}

/**
 * Hook to match candidates to a job description (Fast vector search)
 */
export function useMatchCandidates() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({
      jobDescription,
      numResults = 5,
    }: {
      jobDescription: string;
      numResults?: number;
    }) => hrAgentClient.matchCandidates(jobDescription, numResults),
    onSuccess: (data) => {
      toast.success(`Found ${data.total_found} matching candidates in ${data.query_time_seconds}s`);
      // Invalidate candidates list to refresh any cached data
      queryClient.invalidateQueries({ queryKey: hrAgentKeys.candidates() });
    },
    onError: (error: Error) => {
      toast.error(`Failed to match candidates: ${error.message}`);
    },
  });
}

/**
 * Hook to match candidates using AI agent reasoning (Slow but detailed)
 */
export function useMatchCandidatesWithAgent() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({
      jobDescription,
      numResults = 5,
    }: {
      jobDescription: string;
      numResults?: number;
    }) => hrAgentClient.matchCandidatesWithAgent(jobDescription, numResults),
    onSuccess: (data) => {
      toast.success(`AI Agent found ${data.total_found} matching candidates in ${data.query_time_seconds}s`);
      // Invalidate candidates list to refresh any cached data
      queryClient.invalidateQueries({ queryKey: hrAgentKeys.candidates() });
    },
    onError: (error: Error) => {
      toast.error(`AI Agent search failed: ${error.message}`);
    },
  });
}

/**
 * Hook to upload a resume
 */
export function useUploadResume() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (file: File) => hrAgentClient.uploadResume(file),
    onSuccess: (data) => {
      toast.success(data.message);

      // Invalidate candidates and stats to show the new upload
      queryClient.invalidateQueries({ queryKey: hrAgentKeys.candidates() });
      queryClient.invalidateQueries({ queryKey: hrAgentKeys.stats() });
    },
    onError: (error: Error) => {
      toast.error(`Failed to upload resume: ${error.message}`);
    },
  });
}

/**
 * Hook to get list of candidates
 */
export function useCandidatesList(limit: number = 10, offset: number = 0) {
  return useQuery({
    queryKey: hrAgentKeys.candidatesList(limit, offset),
    queryFn: () => hrAgentClient.listCandidates(limit, offset),
    staleTime: 5 * 60 * 1000, // Consider data fresh for 5 minutes
  });
}

/**
 * Hook to get database statistics
 */
export function useStats() {
  return useQuery({
    queryKey: hrAgentKeys.stats(),
    queryFn: () => hrAgentClient.getStats(),
    staleTime: 10 * 60 * 1000, // Consider data fresh for 10 minutes
  });
}

/**
 * Hook to prefetch candidates list (useful for pagination)
 */
export function usePrefetchCandidates() {
  const queryClient = useQueryClient();

  return (limit: number, offset: number) => {
    queryClient.prefetchQuery({
      queryKey: hrAgentKeys.candidatesList(limit, offset),
      queryFn: () => hrAgentClient.listCandidates(limit, offset),
    });
  };
}
