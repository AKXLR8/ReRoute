import { useEffect } from 'react';
import { initToast, useToast } from '../lib/toast';

export function ToastInitializer() {
  const toast = useToast();
  useEffect(() => { initToast(toast); }, [toast]);
  return null;
}