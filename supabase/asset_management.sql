-- Asset inventory, employee custody, requests, and immutable assignment history.
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE TABLE IF NOT EXISTS public.asset_categories (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  name TEXT NOT NULL UNIQUE,
  description TEXT,
  requires_return BOOLEAN NOT NULL DEFAULT true,
  active BOOLEAN NOT NULL DEFAULT true,
  created_by UUID REFERENCES public.users(id) ON DELETE SET NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.asset_catalog (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  category_id UUID NOT NULL REFERENCES public.asset_categories(id),
  name TEXT NOT NULL,
  manufacturer TEXT,
  model TEXT,
  tracking_mode TEXT NOT NULL CHECK (tracking_mode IN ('serialized', 'bulk')),
  notes TEXT,
  active BOOLEAN NOT NULL DEFAULT true,
  created_by UUID REFERENCES public.users(id) ON DELETE SET NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (category_id, name, manufacturer, model)
);
CREATE INDEX IF NOT EXISTS asset_catalog_active_category_idx ON public.asset_catalog (category_id, active, name);

CREATE TABLE IF NOT EXISTS public.asset_items (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  catalog_id UUID NOT NULL REFERENCES public.asset_catalog(id),
  asset_tag TEXT NOT NULL UNIQUE,
  serial_number TEXT UNIQUE,
  department TEXT,
  location TEXT,
  purchase_date DATE,
  purchase_cost NUMERIC(14,2) CHECK (purchase_cost IS NULL OR purchase_cost >= 0),
  warranty_expires_at DATE,
  condition TEXT NOT NULL DEFAULT 'new' CHECK (condition IN ('new', 'good', 'fair', 'damaged')),
  status TEXT NOT NULL DEFAULT 'available' CHECK (status IN ('available', 'issued', 'returned', 'maintenance', 'lost', 'retired')),
  notes TEXT,
  created_by UUID REFERENCES public.users(id) ON DELETE SET NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS asset_items_scope_status_idx ON public.asset_items (department, status, catalog_id);
CREATE UNIQUE INDEX IF NOT EXISTS asset_items_asset_tag_ci_unique_idx ON public.asset_items (lower(asset_tag));
CREATE UNIQUE INDEX IF NOT EXISTS asset_items_serial_ci_unique_idx ON public.asset_items (lower(serial_number)) WHERE serial_number IS NOT NULL;

CREATE TABLE IF NOT EXISTS public.asset_stock_balances (
  catalog_id UUID PRIMARY KEY REFERENCES public.asset_catalog(id),
  quantity_total INTEGER NOT NULL DEFAULT 0 CHECK (quantity_total >= 0),
  quantity_available INTEGER NOT NULL DEFAULT 0 CHECK (quantity_available >= 0 AND quantity_available <= quantity_total),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.asset_requests (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  employee_id UUID NOT NULL REFERENCES public.users(id),
  department TEXT,
  requested_by UUID NOT NULL REFERENCES public.users(id),
  status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'rejected', 'cancelled', 'fulfilled')),
  reason TEXT,
  decision_note TEXT,
  reviewed_by UUID REFERENCES public.users(id) ON DELETE SET NULL,
  reviewed_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS asset_requests_employee_status_idx ON public.asset_requests (employee_id, status, created_at DESC);
CREATE INDEX IF NOT EXISTS asset_requests_status_idx ON public.asset_requests (status, created_at DESC);

CREATE TABLE IF NOT EXISTS public.asset_request_items (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  request_id UUID NOT NULL REFERENCES public.asset_requests(id) ON DELETE CASCADE,
  catalog_id UUID NOT NULL REFERENCES public.asset_catalog(id),
  quantity INTEGER NOT NULL CHECK (quantity > 0),
  notes TEXT
);

CREATE TABLE IF NOT EXISTS public.asset_assignments (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  employee_id UUID NOT NULL REFERENCES public.users(id),
  department TEXT,
  catalog_id UUID NOT NULL REFERENCES public.asset_catalog(id),
  asset_item_id UUID REFERENCES public.asset_items(id),
  request_id UUID REFERENCES public.asset_requests(id) ON DELETE SET NULL,
  quantity INTEGER NOT NULL DEFAULT 1 CHECK (quantity > 0),
  returned_quantity INTEGER NOT NULL DEFAULT 0 CHECK (returned_quantity >= 0 AND returned_quantity <= quantity),
  assigned_by UUID REFERENCES public.users(id) ON DELETE SET NULL,
  issue_date DATE NOT NULL DEFAULT CURRENT_DATE,
  due_date DATE,
  status TEXT NOT NULL DEFAULT 'issued' CHECK (status IN ('issued', 'partially_returned', 'return_requested', 'returned', 'overdue', 'lost')),
  acknowledged_at TIMESTAMPTZ,
  notes TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CHECK (due_date IS NULL OR due_date >= issue_date),
  CHECK ((asset_item_id IS NULL AND quantity >= 1) OR (asset_item_id IS NOT NULL AND quantity = 1))
);
ALTER TABLE public.asset_assignments ADD COLUMN IF NOT EXISTS department TEXT;
CREATE UNIQUE INDEX IF NOT EXISTS asset_assignments_one_active_unit_idx ON public.asset_assignments (asset_item_id) WHERE asset_item_id IS NOT NULL AND status IN ('issued', 'partially_returned', 'return_requested', 'overdue');
CREATE INDEX IF NOT EXISTS asset_assignments_employee_status_idx ON public.asset_assignments (employee_id, status, issue_date DESC);
CREATE INDEX IF NOT EXISTS asset_assignments_catalog_status_idx ON public.asset_assignments (catalog_id, status);

CREATE TABLE IF NOT EXISTS public.asset_assignment_events (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  assignment_id UUID NOT NULL REFERENCES public.asset_assignments(id) ON DELETE CASCADE,
  actor_id UUID REFERENCES public.users(id) ON DELETE SET NULL,
  event_type TEXT NOT NULL CHECK (event_type IN ('issued', 'acknowledged', 'return_requested', 'partially_returned', 'returned', 'damaged', 'lost', 'status_changed')),
  quantity INTEGER NOT NULL DEFAULT 0 CHECK (quantity >= 0),
  condition TEXT,
  notes TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS asset_assignment_events_history_idx ON public.asset_assignment_events (assignment_id, created_at DESC);

CREATE TABLE IF NOT EXISTS public.asset_stock_movements (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  catalog_id UUID NOT NULL REFERENCES public.asset_catalog(id),
  assignment_id UUID REFERENCES public.asset_assignments(id) ON DELETE SET NULL,
  actor_id UUID REFERENCES public.users(id) ON DELETE SET NULL,
  movement_type TEXT NOT NULL CHECK (movement_type IN ('received', 'issued', 'returned', 'damaged_return', 'lost', 'adjustment')),
  quantity_change INTEGER NOT NULL,
  reference TEXT,
  notes TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS asset_stock_movements_catalog_history_idx ON public.asset_stock_movements (catalog_id, created_at DESC);

INSERT INTO public.asset_categories (name, description, requires_return) VALUES
  ('IT Equipment', 'Computers, peripherals, and other IT equipment', true),
  ('ID Cards', 'Employee identity and access cards', true),
  ('Gifts', 'Company gifts and welcome kits', false),
  ('Office Equipment', 'Shared or assigned office equipment', true)
ON CONFLICT (name) DO NOTHING;

CREATE OR REPLACE FUNCTION public.receive_asset_stock(
  p_catalog_id UUID, p_actor_id UUID, p_quantity INTEGER, p_reference TEXT, p_notes TEXT
) RETURNS JSONB LANGUAGE plpgsql SECURITY INVOKER AS $$
DECLARE
  v_balance public.asset_stock_balances%ROWTYPE;
BEGIN
  IF p_quantity < 1 THEN RAISE EXCEPTION 'Received quantity must be positive'; END IF;
  IF NOT EXISTS (SELECT 1 FROM public.asset_catalog WHERE id=p_catalog_id AND active=true AND tracking_mode='bulk') THEN
    RAISE EXCEPTION 'Active bulk asset type not found';
  END IF;
  INSERT INTO public.asset_stock_balances (catalog_id,quantity_total,quantity_available)
  VALUES (p_catalog_id,p_quantity,p_quantity)
  ON CONFLICT (catalog_id) DO UPDATE SET quantity_total=asset_stock_balances.quantity_total+p_quantity, quantity_available=asset_stock_balances.quantity_available+p_quantity, updated_at=now()
  RETURNING * INTO v_balance;
  INSERT INTO public.asset_stock_movements (catalog_id,actor_id,movement_type,quantity_change,reference,notes)
  VALUES (p_catalog_id,p_actor_id,'received',p_quantity,p_reference,p_notes);
  RETURN to_jsonb(v_balance);
END;
$$;

CREATE OR REPLACE FUNCTION public.issue_assets(
  p_actor_id UUID, p_lines JSONB, p_issue_date DATE, p_due_date DATE, p_notes TEXT
) RETURNS JSONB LANGUAGE plpgsql SECURITY INVOKER AS $$
DECLARE
  line JSONB;
  v_employee UUID;
  v_catalog UUID;
  v_item UUID;
  v_request UUID;
  v_quantity INTEGER;
  v_mode TEXT;
  v_status TEXT;
  v_department TEXT;
  v_available INTEGER;
  v_assignment UUID;
  v_ids JSONB := '[]'::JSONB;
BEGIN
  IF p_due_date IS NOT NULL AND p_due_date < p_issue_date THEN RAISE EXCEPTION 'Due date cannot be earlier than issue date'; END IF;
  FOR line IN SELECT value FROM jsonb_array_elements(p_lines) LOOP
    v_employee := (line->>'employee_id')::UUID;
    v_catalog := (line->>'catalog_id')::UUID;
    v_item := NULLIF(line->>'asset_item_id', '')::UUID;
    v_request := NULLIF(line->>'request_id', '')::UUID;
    v_quantity := COALESCE((line->>'quantity')::INTEGER, 1);
    SELECT department INTO v_department FROM public.users WHERE id=v_employee AND status='active';
    IF NOT FOUND THEN RAISE EXCEPTION 'An employee in this issue batch is inactive or missing'; END IF;
    SELECT tracking_mode INTO v_mode FROM public.asset_catalog WHERE id=v_catalog AND active=true FOR UPDATE;
    IF v_mode IS NULL THEN RAISE EXCEPTION 'An asset catalog item is unavailable'; END IF;
    IF v_mode='serialized' THEN
      IF v_quantity<>1 THEN RAISE EXCEPTION 'Serialized assets are issued one physical item per employee'; END IF;
      IF v_item IS NULL THEN
        SELECT id INTO v_item FROM public.asset_items WHERE catalog_id=v_catalog AND status IN ('available','returned') ORDER BY created_at LIMIT 1 FOR UPDATE SKIP LOCKED;
      END IF;
      IF v_item IS NULL THEN RAISE EXCEPTION 'No physical unit is available for a recipient'; END IF;
      SELECT status INTO v_status FROM public.asset_items WHERE id=v_item AND catalog_id=v_catalog FOR UPDATE;
      IF v_status NOT IN ('available','returned') OR v_status IS NULL THEN RAISE EXCEPTION 'A selected asset item is no longer available'; END IF;
      UPDATE public.asset_items SET status='issued', department=v_department, updated_at=now() WHERE id=v_item;
    ELSE
      IF v_item IS NOT NULL THEN RAISE EXCEPTION 'Bulk stock does not accept a serialized item id'; END IF;
      SELECT quantity_available INTO v_available FROM public.asset_stock_balances WHERE catalog_id=v_catalog FOR UPDATE;
      IF v_available IS NULL OR v_available < v_quantity THEN RAISE EXCEPTION 'Not enough available stock'; END IF;
      UPDATE public.asset_stock_balances SET quantity_available=quantity_available-v_quantity, updated_at=now() WHERE catalog_id=v_catalog;
    END IF;
    INSERT INTO public.asset_assignments (employee_id,department,catalog_id,asset_item_id,request_id,quantity,assigned_by,issue_date,due_date,status,notes)
    VALUES (v_employee,v_department,v_catalog,v_item,v_request,v_quantity,p_actor_id,p_issue_date,p_due_date,'issued',p_notes) RETURNING id INTO v_assignment;
    INSERT INTO public.asset_assignment_events (assignment_id,actor_id,event_type,quantity,notes)
    VALUES (v_assignment,p_actor_id,'issued',v_quantity,p_notes);
    IF v_mode='bulk' THEN
      INSERT INTO public.asset_stock_movements (catalog_id,assignment_id,actor_id,movement_type,quantity_change,notes)
      VALUES (v_catalog,v_assignment,p_actor_id,'issued',-v_quantity,p_notes);
    END IF;
    v_ids := v_ids || jsonb_build_array(v_assignment);
  END LOOP;
  IF v_request IS NOT NULL THEN
    UPDATE public.asset_requests SET status='fulfilled', updated_at=now() WHERE id=v_request AND status='approved';
    IF NOT FOUND THEN RAISE EXCEPTION 'The approved asset request changed before it could be fulfilled'; END IF;
  END IF;
  RETURN v_ids;
END;
$$;

CREATE OR REPLACE FUNCTION public.complete_asset_return(
  p_assignment_id UUID, p_actor_id UUID, p_quantity INTEGER, p_condition TEXT, p_notes TEXT
) RETURNS JSONB LANGUAGE plpgsql SECURITY INVOKER AS $$
DECLARE
  a public.asset_assignments%ROWTYPE;
  v_remaining INTEGER;
  v_status TEXT;
BEGIN
  SELECT * INTO a FROM public.asset_assignments WHERE id=p_assignment_id FOR UPDATE;
  IF NOT FOUND OR a.status NOT IN ('issued','partially_returned','return_requested','overdue') THEN RAISE EXCEPTION 'This assignment cannot be returned'; END IF;
  v_remaining := a.quantity-a.returned_quantity;
  IF p_quantity < 1 OR p_quantity > v_remaining THEN RAISE EXCEPTION 'Return quantity exceeds the outstanding quantity'; END IF;
  IF p_condition='lost' AND p_quantity<>v_remaining THEN RAISE EXCEPTION 'Mark all outstanding units lost together'; END IF;
  IF a.asset_item_id IS NOT NULL AND p_quantity<>1 THEN RAISE EXCEPTION 'A serialized asset must be returned as one physical item'; END IF;
  IF p_condition NOT IN ('new','good','fair','damaged','lost') THEN RAISE EXCEPTION 'Unsupported return condition'; END IF;
  IF p_condition='lost' THEN
    v_status := 'lost';
    IF a.asset_item_id IS NOT NULL THEN UPDATE public.asset_items SET status='lost',condition='damaged',updated_at=now() WHERE id=a.asset_item_id; END IF;
  ELSE
    v_status := CASE WHEN a.returned_quantity+p_quantity=a.quantity THEN 'returned' ELSE 'partially_returned' END;
    IF a.asset_item_id IS NOT NULL THEN
      UPDATE public.asset_items SET status=CASE WHEN p_condition='damaged' THEN 'maintenance' ELSE 'returned' END, condition=p_condition, updated_at=now() WHERE id=a.asset_item_id;
    ELSIF p_condition='damaged' THEN
      UPDATE public.asset_stock_balances SET quantity_total=quantity_total-p_quantity, updated_at=now() WHERE catalog_id=a.catalog_id;
      INSERT INTO public.asset_stock_movements (catalog_id,assignment_id,actor_id,movement_type,quantity_change,notes)
      VALUES (a.catalog_id,a.id,p_actor_id,'damaged_return',-p_quantity,p_notes);
    ELSE
      UPDATE public.asset_stock_balances SET quantity_available=quantity_available+p_quantity, updated_at=now() WHERE catalog_id=a.catalog_id;
      INSERT INTO public.asset_stock_movements (catalog_id,assignment_id,actor_id,movement_type,quantity_change,notes)
      VALUES (a.catalog_id,a.id,p_actor_id,'returned',p_quantity,p_notes);
    END IF;
  END IF;
  UPDATE public.asset_assignments SET returned_quantity=returned_quantity+p_quantity,status=v_status,updated_at=now() WHERE id=a.id;
  INSERT INTO public.asset_assignment_events (assignment_id,actor_id,event_type,quantity,condition,notes)
  VALUES (a.id,p_actor_id,CASE WHEN p_condition='lost' THEN 'lost' WHEN p_condition='damaged' THEN 'damaged' WHEN v_status='returned' THEN 'returned' ELSE 'partially_returned' END,p_quantity,p_condition,p_notes);
  IF p_condition='lost' AND a.asset_item_id IS NULL THEN
    UPDATE public.asset_stock_balances SET quantity_total=quantity_total-p_quantity, updated_at=now() WHERE catalog_id=a.catalog_id;
    INSERT INTO public.asset_stock_movements (catalog_id,assignment_id,actor_id,movement_type,quantity_change,notes)
    VALUES (a.catalog_id,a.id,p_actor_id,'lost',-p_quantity,p_notes);
  END IF;
  RETURN (SELECT to_jsonb(x) FROM public.asset_assignments x WHERE x.id=a.id);
END;
$$;

UPDATE public.permissions SET permissions=array_append(permissions,'manage_assets'),updated_at=now()
WHERE role IN ('hr','director','super_admin') AND NOT ('manage_assets'=ANY(permissions));
UPDATE public.permissions SET permissions=array_append(permissions,'view_department_assets'),updated_at=now()
WHERE role='manager' AND NOT ('view_department_assets'=ANY(permissions));
UPDATE public.permissions SET permissions=array_append(permissions,'view_reporting_assets'),updated_at=now()
WHERE role='lead' AND NOT ('view_reporting_assets'=ANY(permissions));
UPDATE public.permissions SET permissions=array_append(permissions,'view_own_assets'),updated_at=now()
WHERE role='employee' AND NOT ('view_own_assets'=ANY(permissions));

REVOKE ALL ON FUNCTION public.issue_assets(UUID,JSONB,DATE,DATE,TEXT) FROM PUBLIC;
REVOKE ALL ON FUNCTION public.complete_asset_return(UUID,UUID,INTEGER,TEXT,TEXT) FROM PUBLIC;
REVOKE ALL ON FUNCTION public.receive_asset_stock(UUID,UUID,INTEGER,TEXT,TEXT) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.issue_assets(UUID,JSONB,DATE,DATE,TEXT) TO service_role;
GRANT EXECUTE ON FUNCTION public.complete_asset_return(UUID,UUID,INTEGER,TEXT,TEXT) TO service_role;
GRANT EXECUTE ON FUNCTION public.receive_asset_stock(UUID,UUID,INTEGER,TEXT,TEXT) TO service_role;

ALTER TABLE public.asset_categories ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.asset_catalog ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.asset_items ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.asset_stock_balances ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.asset_requests ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.asset_request_items ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.asset_assignments ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.asset_assignment_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.asset_stock_movements ENABLE ROW LEVEL SECURITY;

