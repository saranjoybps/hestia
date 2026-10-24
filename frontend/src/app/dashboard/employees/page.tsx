import { cookies } from 'next/headers';
import EmployeesClientPage from './EmployeesClient';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api';

async function getJson(path: string, token: string) {
  try {
    const response = await fetch(`${API_BASE_URL}${path}`, {
      headers: { Authorization: `Bearer ${token}` },
      cache: 'no-store',
    });
    return response.ok ? response.json() : null;
  } catch {
    return null;
  }
}

export default async function EmployeesPage() {
  const cookieStore = await cookies();
  const token = cookieStore.get('hestia_session')?.value || cookieStore.get('joyhr_session')?.value;

  if (!token) {
    return <EmployeesClientPage initialData={{ employees: [], inactiveEmployees: [], departments: [], activeCount: 0, inactiveCount: 0, total: 0, totalPages: 1, serverFetched: false }} />;
  }

  const me = await getJson('/users/me', token);
  if (!me) {
    return <EmployeesClientPage initialData={{ employees: [], inactiveEmployees: [], departments: [], activeCount: 0, inactiveCount: 0, total: 0, totalPages: 1, serverFetched: false }} />;
  }
  const role = me?.role;
  const [employeeResult, inactiveEmployeeResult, activeResult, inactiveResult, departmentResult, reporteeResult, managerResult, requestResult] = await Promise.all([
    getJson('/users?status=active&page=1&limit=20', token),
    getJson('/users?status=inactive&page=1&limit=20', token),
    getJson('/users?status=active&page=1&limit=1', token),
    getJson('/users?status=inactive&page=1&limit=1', token),
    getJson('/departments', token),
    ['lead', 'manager', 'director'].includes(role) ? getJson(`/users/${me.uid}/reportees`, token) : Promise.resolve(null),
    ['hr', 'director'].includes(role) ? getJson('/users?role=manager&role=lead&role=director&page=1&limit=50', token) : Promise.resolve(null),
    role === 'director' ? getJson('/onboarding/requests?status=pending', token) : role === 'hr' ? getJson('/onboarding/requests', token) : Promise.resolve(null),
  ]);

  const rawEmployees = Array.isArray(employeeResult?.users) ? employeeResult.users : [];
  const normalizeEmployee = (employee: any) => ({
    ...employee,
    lastName: employee.last_name ?? employee.lastName,
    managerId: employee.manager_id ?? employee.managerId,
  });
  const employees = rawEmployees.map(normalizeEmployee);
  const inactiveEmployees = Array.isArray(inactiveEmployeeResult?.users) ? inactiveEmployeeResult.users.map(normalizeEmployee) : [];
  const reportees = Array.isArray(reporteeResult) ? reporteeResult.map((employee: any) => ({
    ...employee,
    lastName: employee.last_name ?? employee.lastName,
  })) : [];
  const managers = Array.isArray(managerResult?.users) ? managerResult.users.map((employee: any) => ({
    ...employee,
    lastName: employee.last_name ?? employee.lastName,
    managerId: employee.manager_id ?? employee.managerId,
  })) : [];
  const requests = Array.isArray(requestResult) ? requestResult.map((request: any) => ({
    ...request,
    lastName: request.last_name ?? request.lastName,
  })) : [];

  return (
    <EmployeesClientPage
      initialData={{
        employees,
        inactiveEmployees,
        departments: Array.isArray(departmentResult?.departments) ? departmentResult.departments : [],
        activeCount: activeResult?.total ?? 0,
        inactiveCount: inactiveResult?.total ?? 0,
        total: employeeResult?.total ?? employees.length,
        totalPages: employeeResult?.totalPages ?? 1,
        reportees,
        managers,
        pendingRequests: role === 'director' ? requests : [],
        myRequests: role === 'hr' ? requests : [],
        serverFetched: Boolean(me),
      }}
    />
  );
}
