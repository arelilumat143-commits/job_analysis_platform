#!/bin/bash
cd /root/projects/job_analysis_platform/web/frontend
setsid npm run dev -- --host 0.0.0.0 > /tmp/vite_dev.log 2>&1 < /dev/null &
disown
echo "Vite started, PID: $!"
