'use server';

import { updateTag } from 'next/cache';
import { cookies } from 'next/headers';

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api';

async function fetchJson<T>(path: string, init?: RequestInit): Promise<T> {
  const cookieStore = await cookies();
  const token = cookieStore.get('hestia_session')?.value || cookieStore.get('joyhr_session')?.value;
  if (!token) throw new Error('Authentication required');
  const res = await fetch(`${API}${path}`, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
      ...(init?.headers || {}),
    },
    cache: 'no-store',
  });
  if (!res.ok) throw new Error(`API ${res.status}: ${await res.text()}`);
  return res.json();
}

export async function createEmployee(form: FormData) {
  const payload = {
    email: form.get('email'),
    name: form.get('name'),
    last_name: form.get('lastName') || '',
    password: form.get('password') || '',
    role: form.get('role'),
    department: form.get('department'),
    designation: form.get('designation'),
    phone: form.get('phone') || '',
    dateOfJoining: form.get('dateOfJoining') || null,
    manager_id: form.get('managerId') || null,
    lead_id: null,
    status: 'active',
  };
  await fetchJson(`/users/register`, { method: 'POST', body: JSON.stringify(payload) });
  updateTag('employees');
}

export async function updateEmployee(uid: string, form: FormData) {
  const payload = {
    name: form.get('name'),
    last_name: form.get('lastName') || '',
    role: form.get('role'),
    department: form.get('department'),
    designation: form.get('designation'),
    phone: form.get('phone') || '',
    dateOfJoining: form.get('dateOfJoining') || null,
    manager_id: form.get('managerId') || null,
    lead_id: null,
  };
  await fetchJson(`/users/${uid}`, { method: 'PUT', body: JSON.stringify(payload) });
  updateTag('employees');
}

export async function deactivateEmployee(uid: string) {
  await fetchJson(`/users/${uid}`, { method: 'DELETE' });
  updateTag('employees');
}

export async function activateEmployee(uid: string) {
  await fetchJson(`/users/${uid}/activate`, { method: 'POST' });
  updateTag('employees');
}

export async function approveRequest(id: string) {
  await fetchJson(`/onboarding/requests/${id}/approve`, { method: 'PATCH' });
  updateTag('employees');
}

export async function rejectRequest(id: string, reason: string) {
  await fetchJson(`/onboarding/requests/${id}/reject`, {
    method: 'PATCH',
    body: JSON.stringify({ rejection_reason: reason }),
  });
  updateTag('employees');
}

export async function deleteRequest(id: string) {
  await fetchJson(`/onboarding/requests/${id}`, { method: 'DELETE' });
  updateTag('employees');
}
