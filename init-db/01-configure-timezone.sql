-- 01-configure-timezone.sql
-- Configure timezone settings for consistent datetime handling

-- Set global timezone to UTC
-- This ensures all datetime operations are in UTC by default
SET GLOBAL time_zone = '+00:00';

-- Set session timezone to UTC for this initialization session
SET time_zone = '+00:00';
