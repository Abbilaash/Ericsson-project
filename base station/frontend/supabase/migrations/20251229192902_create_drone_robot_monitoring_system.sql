/*
  # Drone and Robot Monitoring System

  1. New Tables
    - `drones`
      - `id` (text, primary key) - Drone identifier
      - `battery_percent` (integer) - Battery level 0-100
      - `status` (text) - ACTIVE / LOW / HANDOVER
      - `last_seen` (timestamptz) - Last communication time
      - `role` (text) - INSPECTING / IDLE
      - `position_x` (numeric) - X coordinate
      - `position_y` (numeric) - Y coordinate
      - `height` (numeric) - Height/Z coordinate
      - `created_at` (timestamptz) - Record creation time
      - `updated_at` (timestamptz) - Last update time
    
    - `robots`
      - `id` (text, primary key) - Robot identifier
      - `battery_percent` (integer) - Battery level 0-100
      - `busy` (boolean) - Busy or Idle
      - `current_task_id` (text) - Reference to current task
      - `position_x` (numeric) - X coordinate
      - `position_y` (numeric) - Y coordinate
      - `height` (numeric) - Height on tower
      - `created_at` (timestamptz) - Record creation time
      - `updated_at` (timestamptz) - Last update time
    
    - `tasks`
      - `id` (text, primary key) - Task identifier
      - `type` (text) - Task type description
      - `status` (text) - UNCLAIMED / CLAIMED / DONE
      - `claimed_by` (text) - ID of drone/robot that claimed task
      - `time_detected` (timestamptz) - When task was detected
      - `created_at` (timestamptz) - Record creation time
      - `updated_at` (timestamptz) - Last update time
    
    - `logs`
      - `id` (uuid, primary key) - Log entry identifier
      - `timestamp` (timestamptz) - Log timestamp
      - `sender_id` (text) - ID of sender
      - `sender_role` (text) - DRONE / ROBOT
      - `message_type` (text) - REQUEST / ACK / etc
      - `task_id` (text) - Related task ID if any
      - `raw_json` (jsonb) - Full message data
      - `created_at` (timestamptz) - Record creation time

  2. Security
    - Enable RLS on all tables
    - Add policies for public read access (for demo purposes)
*/

CREATE TABLE IF NOT EXISTS drones (
  id text PRIMARY KEY,
  battery_percent integer NOT NULL DEFAULT 100,
  status text NOT NULL DEFAULT 'ACTIVE',
  last_seen timestamptz DEFAULT now(),
  role text NOT NULL DEFAULT 'IDLE',
  position_x numeric DEFAULT 0,
  position_y numeric DEFAULT 0,
  height numeric DEFAULT 0,
  created_at timestamptz DEFAULT now(),
  updated_at timestamptz DEFAULT now()
);

CREATE TABLE IF NOT EXISTS robots (
  id text PRIMARY KEY,
  battery_percent integer NOT NULL DEFAULT 100,
  busy boolean DEFAULT false,
  current_task_id text,
  position_x numeric DEFAULT 0,
  position_y numeric DEFAULT 0,
  height numeric DEFAULT 0,
  created_at timestamptz DEFAULT now(),
  updated_at timestamptz DEFAULT now()
);

CREATE TABLE IF NOT EXISTS tasks (
  id text PRIMARY KEY,
  type text NOT NULL,
  status text NOT NULL DEFAULT 'UNCLAIMED',
  claimed_by text,
  time_detected timestamptz DEFAULT now(),
  created_at timestamptz DEFAULT now(),
  updated_at timestamptz DEFAULT now()
);

CREATE TABLE IF NOT EXISTS logs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  timestamp timestamptz DEFAULT now(),
  sender_id text NOT NULL,
  sender_role text NOT NULL,
  message_type text NOT NULL,
  task_id text,
  raw_json jsonb,
  created_at timestamptz DEFAULT now()
);

ALTER TABLE drones ENABLE ROW LEVEL SECURITY;
ALTER TABLE robots ENABLE ROW LEVEL SECURITY;
ALTER TABLE tasks ENABLE ROW LEVEL SECURITY;
ALTER TABLE logs ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Allow public read access to drones"
  ON drones FOR SELECT
  TO anon
  USING (true);

CREATE POLICY "Allow public insert to drones"
  ON drones FOR INSERT
  TO anon
  WITH CHECK (true);

CREATE POLICY "Allow public update to drones"
  ON drones FOR UPDATE
  TO anon
  USING (true)
  WITH CHECK (true);

CREATE POLICY "Allow public read access to robots"
  ON robots FOR SELECT
  TO anon
  USING (true);

CREATE POLICY "Allow public insert to robots"
  ON robots FOR INSERT
  TO anon
  WITH CHECK (true);

CREATE POLICY "Allow public update to robots"
  ON robots FOR UPDATE
  TO anon
  USING (true)
  WITH CHECK (true);

CREATE POLICY "Allow public read access to tasks"
  ON tasks FOR SELECT
  TO anon
  USING (true);

CREATE POLICY "Allow public insert to tasks"
  ON tasks FOR INSERT
  TO anon
  WITH CHECK (true);

CREATE POLICY "Allow public update to tasks"
  ON tasks FOR UPDATE
  TO anon
  USING (true)
  WITH CHECK (true);

CREATE POLICY "Allow public read access to logs"
  ON logs FOR SELECT
  TO anon
  USING (true);

CREATE POLICY "Allow public insert to logs"
  ON logs FOR INSERT
  TO anon
  WITH CHECK (true);