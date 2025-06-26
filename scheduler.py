from datetime import datetime, timedelta, date, time as dt_time

def get_models():
    """Get model classes and db object - lazy import to avoid circular imports"""
    from models import Job, Schedule, Procedure, db
    return Job, Schedule, Procedure, db

def get_working_hours(date):
    """
    Get working hours for a given date
    Monday-Friday: 8:15 AM - 1:00 PM, 1:30 PM - 5:00 PM (8.75 hours total)
    Saturday: 8:15 AM - 1:00 PM, 1:30 PM - 3:30 PM (6.75 hours total)
    Sunday: No work
    """
    if date.weekday() == 6:  # Sunday
        return []
    
    start_time = datetime.combine(date, dt_time(8, 15))  # 8:15 AM
    lunch_start = datetime.combine(date, dt_time(13, 0))  # 1:00 PM
    lunch_end = datetime.combine(date, dt_time(13, 30))   # 1:30 PM
    
    if date.weekday() < 5:  # Monday to Friday
        end_time = datetime.combine(date, dt_time(17, 0))  # 5:00 PM
    else:  # Saturday
        end_time = datetime.combine(date, dt_time(15, 30))  # 3:30 PM
    
    return [(start_time, lunch_start), (lunch_end, end_time)]

def is_working_day(date):
    """Check if the given date is a working day (Monday to Saturday)"""
    return date.weekday() < 6  # 0-5 for Monday-Saturday

def get_previous_working_day(date):
    """Get the previous working day before the given date"""
    prev_date = date - timedelta(days=1)
    while not is_working_day(prev_date):
        prev_date -= timedelta(days=1)
    return prev_date

def get_next_working_day(date):
    """Get the next working day after the given date"""
    next_date = date + timedelta(days=1)
    while not is_working_day(next_date):
        next_date += timedelta(days=1)
    return next_date

def get_completion_target_datetime(deadline_date, deadline_time):
    """
    Get the target completion datetime (two days before deadline)
    Job must be completed by end of working day two days before deadline
    """
    # Go back 2 working days from deadline
    target_date = get_previous_working_day(deadline_date)  # 1 day back
    target_date = get_previous_working_day(target_date)    # 2 days back
    blocks = get_working_hours(target_date)
    if blocks:
        return blocks[-1][1]  # End of last working block
    return datetime.combine(target_date, dt_time(17, 0))

def minutes_to_timedelta(minutes):
    """Convert minutes to timedelta"""
    return timedelta(minutes=minutes)

def find_available_slot_backward(procedure_id, procedure_duration_minutes, target_end_datetime):
    """
    Find the latest available slot for a procedure working backwards from target end time
    Only one team per procedure - no conflicts allowed across all jobs
    Handles continuous scheduling across multiple working blocks if needed
    """
    Job, Schedule, Procedure, db = get_models()
    
    procedure_duration = minutes_to_timedelta(procedure_duration_minutes)
    current_datetime = target_end_datetime
    search_limit = target_end_datetime.date() - timedelta(days=365)
    
    while current_datetime.date() >= search_limit:
        current_date = current_datetime.date()
        
        if not is_working_day(current_date):
            # Move to previous working day
            prev_working_day = get_previous_working_day(current_date)
            blocks = get_working_hours(prev_working_day)
            if blocks:
                current_datetime = blocks[-1][1]  # End of last block
            else:
                current_datetime = datetime.combine(prev_working_day, dt_time(17, 0))
            continue
        
        blocks = get_working_hours(current_date)
        if not blocks:
            current_datetime = datetime.combine(current_date - timedelta(days=1), dt_time(17, 0))
            continue
        
        # Try blocks from latest to earliest (working backwards)
        for block_start, block_end in reversed(blocks):
            if block_start >= current_datetime:
                continue  # This block is in the future
            
            # Adjust block end to current time if we're in the middle of a block
            effective_end = min(block_end, current_datetime)
            
            # Check available time in this block
            available_time = effective_end - block_start
            
            if available_time >= procedure_duration:
                # Try to place procedure at the end of available time (working backwards)
                candidate_end = effective_end
                candidate_start = candidate_end - procedure_duration
                
                # Ensure it doesn't go before block start
                if candidate_start >= block_start:
                    # Check for conflicts with existing schedules for this procedure (across all jobs)
                    conflicts = Schedule.query.filter(
                        Schedule.procedure_id == procedure_id,
                        Schedule.start_datetime < candidate_end,
                        Schedule.end_datetime > candidate_start
                    ).all()
                    
                    if not conflicts:
                        return candidate_start, candidate_end
                    else:
                        # Find the earliest start time of conflicting schedules
                        earliest_conflict_start = min(conflict.start_datetime for conflict in conflicts)
                        current_datetime = earliest_conflict_start
                        break  # Restart search from before this conflict
            else:
                # Not enough time in this block, move to previous block or previous day
                current_block_index = None
                for i, (start, end) in enumerate(blocks):
                    if (start, end) == (block_start, block_end):
                        current_block_index = i
                        break
                
                if current_block_index is not None and current_block_index == 0:  # First block of the day
                    prev_working_day = get_previous_working_day(current_date)
                    prev_blocks = get_working_hours(prev_working_day)
                    if prev_blocks:
                        current_datetime = prev_blocks[-1][1]  # End of last block
                    else:
                        current_datetime = datetime.combine(prev_working_day, dt_time(17, 0))
                elif current_block_index is not None and current_block_index > 0:
                    # Move to previous block
                    current_datetime = blocks[current_block_index - 1][1]
                else:
                    # Fallback: move to previous day
                    prev_working_day = get_previous_working_day(current_date)
                    prev_blocks = get_working_hours(prev_working_day)
                    if prev_blocks:
                        current_datetime = prev_blocks[-1][1]
                    else:
                        current_datetime = datetime.combine(prev_working_day, dt_time(17, 0))
                break
        else:
            # No suitable block found today, move to previous working day
            prev_working_day = get_previous_working_day(current_date)
            blocks = get_working_hours(prev_working_day)
            if blocks:
                current_datetime = blocks[-1][1]
            else:
                current_datetime = datetime.combine(prev_working_day, dt_time(17, 0))
    
    return None

def find_available_slot_forward(procedure_id, procedure_duration_minutes, start_from_datetime):
    """
    Find the earliest available slot for a procedure starting from a given datetime
    Handles continuous scheduling across multiple working blocks if needed
    """
    Job, Schedule, Procedure, db = get_models()
    
    procedure_duration = minutes_to_timedelta(procedure_duration_minutes)
    current_datetime = start_from_datetime
    search_limit = start_from_datetime.date() + timedelta(days=365)
    
    while current_datetime.date() <= search_limit:
        current_date = current_datetime.date()
        
        if not is_working_day(current_date):
            # Move to next working day
            next_working_day = get_next_working_day(current_date)
            blocks = get_working_hours(next_working_day)
            if blocks:
                current_datetime = blocks[0][0]  # Start of first block
            else:
                current_datetime = datetime.combine(next_working_day, dt_time(8, 15))
            continue
        
        blocks = get_working_hours(current_date)
        if not blocks:
            current_datetime = datetime.combine(current_date + timedelta(days=1), dt_time(8, 15))
            continue
        
        # Find available time starting from current_datetime
        for block_start, block_end in blocks:
            if block_end <= current_datetime:
                continue  # This block is already past
            
            # Adjust block start to current time if we're in the middle of a block
            effective_start = max(block_start, current_datetime)
            
            # Check available time in this block
            available_time = block_end - effective_start
            
            if available_time >= procedure_duration:
                # Try to place procedure at the start of available time
                candidate_start = effective_start
                candidate_end = candidate_start + procedure_duration
                
                # Check for conflicts with existing schedules for this procedure
                conflicts = Schedule.query.filter(
                    Schedule.procedure_id == procedure_id,
                    Schedule.start_datetime < candidate_end,
                    Schedule.end_datetime > candidate_start
                ).all()
                
                if not conflicts:
                    return candidate_start, candidate_end
                else:
                    # Find the earliest end time of conflicting schedules
                    latest_conflict = max(conflict.end_datetime for conflict in conflicts)
                    current_datetime = latest_conflict
                    break  # Restart search from after this conflict
            else:
                # Not enough time in this block, move to next block or next day
                current_block_index = None
                for i, (start, end) in enumerate(blocks):
                    if (start, end) == (block_start, block_end):
                        current_block_index = i
                        break
                
                if current_block_index is not None and current_block_index == len(blocks) - 1:  # Last block of the day
                    next_working_day = get_next_working_day(current_date)
                    next_blocks = get_working_hours(next_working_day)
                    if next_blocks:
                        current_datetime = next_blocks[0][0]
                    else:
                        current_datetime = datetime.combine(next_working_day, dt_time(8, 15))
                elif current_block_index is not None and current_block_index < len(blocks) - 1:
                    # Move to next block
                    current_datetime = blocks[current_block_index + 1][0]
                else:
                    # Fallback: move to next day
                    next_working_day = get_next_working_day(current_date)
                    next_blocks = get_working_hours(next_working_day)
                    if next_blocks:
                        current_datetime = next_blocks[0][0]
                    else:
                        current_datetime = datetime.combine(next_working_day, dt_time(8, 15))
                break
        else:
            # No suitable block found today, move to next working day
            next_working_day = get_next_working_day(current_date)
            blocks = get_working_hours(next_working_day)
            if blocks:
                current_datetime = blocks[0][0]
            else:
                current_datetime = datetime.combine(next_working_day, dt_time(8, 15))
    
    return None

def find_available_slot_backward_multiday(procedure_id, procedure_duration_minutes, target_end_datetime):
    """
    Find the latest available slot for a procedure that may span multiple days
    Returns (start_datetime, end_datetime) where the time span contains exactly the required working hours
    """
    Job, Schedule, Procedure, db = get_models()
    
    procedure_duration = minutes_to_timedelta(procedure_duration_minutes)
    search_start_date = target_end_datetime.date() - timedelta(days=30)
    
    # Start from target end time and work backwards
    current_end_time = target_end_datetime
    
    while current_end_time.date() >= search_start_date:
        remaining_duration = procedure_duration
        schedule_blocks = []
        check_end_time = current_end_time
        
        # Try to build a schedule working backwards
        while remaining_duration > timedelta(0):
            current_date = check_end_time.date()
            
            if not is_working_day(current_date):
                prev_working_day = get_previous_working_day(current_date)
                blocks = get_working_hours(prev_working_day)
                if blocks:
                    check_end_time = blocks[-1][1]
                else:
                    check_end_time = datetime.combine(prev_working_day, dt_time(17, 0))
                continue
            
            blocks = get_working_hours(current_date)
            if not blocks:
                check_end_time = datetime.combine(current_date - timedelta(days=1), dt_time(17, 0))
                continue
            
            # Process blocks for this day (from latest to earliest)
            for block_start, block_end in reversed(blocks):
                if block_end > check_end_time:
                    continue
                
                effective_end = min(block_end, check_end_time)
                available_time = effective_end - block_start
                
                if available_time <= timedelta(0):
                    continue
                
                # Use as much of this block as possible
                time_to_use = min(available_time, remaining_duration)
                block_start_time = effective_end - time_to_use
                
                # Check for conflicts in this block
                conflicts = Schedule.query.filter(
                    Schedule.procedure_id == procedure_id,
                    Schedule.start_datetime < effective_end,
                    Schedule.end_datetime > block_start_time
                ).all()
                
                if conflicts:
                    # Find earliest conflict start and try before it
                    earliest_conflict = min(conflict.start_datetime for conflict in conflicts)
                    if earliest_conflict <= block_start:
                        # Entire block is blocked, try previous block
                        continue
                    else:
                        # Partial block available
                        effective_end = earliest_conflict
                        available_time = effective_end - block_start
                        if available_time <= timedelta(0):
                            continue
                        time_to_use = min(available_time, remaining_duration)
                        block_start_time = effective_end - time_to_use
                
                # Add this block to our schedule
                schedule_blocks.append((block_start_time, block_start_time + time_to_use))
                remaining_duration -= time_to_use
                check_end_time = block_start_time
                
                if remaining_duration <= timedelta(0):
                    break
            
            if remaining_duration > timedelta(0):
                # Move to previous day
                if current_date == search_start_date:
                    break  # Reached search limit
                prev_working_day = get_previous_working_day(current_date)
                blocks = get_working_hours(prev_working_day)
                if blocks:
                    check_end_time = blocks[-1][1]
                else:
                    check_end_time = datetime.combine(prev_working_day, dt_time(17, 0))
        
        # Check if we successfully allocated all time
        if remaining_duration <= timedelta(0) and schedule_blocks:
            # Sort blocks chronologically (earliest first)
            schedule_blocks.sort()
            # Return the start of first block and end of last block
            overall_start = schedule_blocks[0][0]
            overall_end = schedule_blocks[-1][1]
            return overall_start, overall_end
        
        # Try again with an earlier end time
        current_end_time = current_end_time - timedelta(hours=1)
    
    return None

def find_available_slot_forward_multiday(procedure_id, procedure_duration_minutes, start_from_datetime):
    """
    Find the earliest available slot for a procedure that may span multiple days
    Returns None if cannot be scheduled, or (start_datetime, end_datetime) if successful
    """
    Job, Schedule, Procedure, db = get_models()
    
    procedure_duration = minutes_to_timedelta(procedure_duration_minutes)
    search_end_date = start_from_datetime.date() + timedelta(days=30)  # Look ahead up to 30 days
    
    current_start_time = start_from_datetime
    
    while current_start_time.date() <= search_end_date:
        remaining_duration = procedure_duration
        schedule_blocks = []
        check_start_time = current_start_time
        
        # Try to build a schedule working forwards
        while remaining_duration > timedelta(0):
            current_date = check_start_time.date()
            
            if not is_working_day(current_date):
                next_working_day = get_next_working_day(current_date)
                blocks = get_working_hours(next_working_day)
                if blocks:
                    check_start_time = blocks[0][0]
                else:
                    check_start_time = datetime.combine(next_working_day, dt_time(8, 15))
                continue
            
            blocks = get_working_hours(current_date)
            if not blocks:
                check_start_time = datetime.combine(current_date + timedelta(days=1), dt_time(8, 15))
                continue
            
            # Process blocks for this day
            for block_start, block_end in blocks:
                if block_start < check_start_time:
                    block_start = max(block_start, check_start_time)
                
                if block_start >= block_end:
                    continue
                
                block_duration = block_end - block_start
                time_to_use = min(remaining_duration, block_duration)
                
                schedule_blocks.append((block_start, block_start + time_to_use))
                remaining_duration -= time_to_use
                check_start_time = block_end
                
                if remaining_duration <= timedelta(0):
                    break
            
            if remaining_duration > timedelta(0):
                # Move to next day
                if current_date == search_end_date:
                    break  # Reached search limit
                next_working_day = get_next_working_day(current_date)
                blocks = get_working_hours(next_working_day)
                if blocks:
                    check_start_time = blocks[0][0]
                else:
                    check_start_time = datetime.combine(next_working_day, dt_time(8, 15))
        
        # Check if we successfully allocated all time
        if remaining_duration <= timedelta(0) and schedule_blocks:
            # Sort blocks chronologically
            schedule_blocks.sort()
            overall_start = schedule_blocks[0][0]
            overall_end = schedule_blocks[-1][1]
            return overall_start, overall_end
        
        # Try again with a later start time
        current_start_time = current_start_time + timedelta(hours=1)
    
    return None

def find_available_slot_forward_with_memory_conflicts(procedure_id, procedure_duration_minutes, start_from_datetime, memory_conflicts):
    """
    Find the earliest available slot for a procedure starting from a given datetime
    Considers both database conflicts and in-memory conflicts from current scheduling batch
    """
    Job, Schedule, Procedure, db = get_models()
    
    procedure_duration = minutes_to_timedelta(procedure_duration_minutes)
    current_datetime = start_from_datetime
    search_limit = start_from_datetime.date() + timedelta(days=365)
    
    while current_datetime.date() <= search_limit:
        current_date = current_datetime.date()
        
        if not is_working_day(current_date):
            # Move to next working day
            next_working_day = get_next_working_day(current_date)
            blocks = get_working_hours(next_working_day)
            if blocks:
                current_datetime = blocks[0][0]  # Start of first block
            else:
                current_datetime = datetime.combine(next_working_day, dt_time(8, 15))
            continue
        
        blocks = get_working_hours(current_date)
        if not blocks:
            current_datetime = datetime.combine(current_date + timedelta(days=1), dt_time(8, 15))
            continue
        
        # Find available time starting from current_datetime
        for block_start, block_end in blocks:
            if block_end <= current_datetime:
                continue  # This block is already past
            
            # Adjust block start to current time if we're in the middle of a block
            effective_start = max(block_start, current_datetime)
            
            # Check available time in this block
            available_time = block_end - effective_start
            
            if available_time >= procedure_duration:
                # Try to place procedure at the start of available time
                candidate_start = effective_start
                candidate_end = candidate_start + procedure_duration
                
                # Check for conflicts with existing database schedules for this procedure
                db_conflicts = Schedule.query.filter(
                    Schedule.procedure_id == procedure_id,
                    Schedule.start_datetime < candidate_end,
                    Schedule.end_datetime > candidate_start
                ).all()
                
                # Check for conflicts with in-memory schedules
                memory_conflicts_found = [
                    s for s in memory_conflicts 
                    if s['procedure_id'] == procedure_id and
                    s['start_datetime'] < candidate_end and
                    s['end_datetime'] > candidate_start
                ]
                
                if not db_conflicts and not memory_conflicts_found:
                    return candidate_start, candidate_end
                else:
                    # Find the earliest end time of conflicting schedules
                    latest_conflict_end = current_datetime
                    
                    if db_conflicts:
                        latest_conflict_end = max(latest_conflict_end, 
                                                max(conflict.end_datetime for conflict in db_conflicts))
                    
                    if memory_conflicts_found:
                        latest_conflict_end = max(latest_conflict_end,
                                                max(conflict['end_datetime'] for conflict in memory_conflicts_found))
                    
                    current_datetime = latest_conflict_end
                    break  # Restart search from after this conflict
            else:
                # Not enough time in this block, move to next block or next day
                current_block_index = None
                for i, (start, end) in enumerate(blocks):
                    if (start, end) == (block_start, block_end):
                        current_block_index = i
                        break
                
                if current_block_index is not None and current_block_index == len(blocks) - 1:  # Last block of the day
                    next_working_day = get_next_working_day(current_date)
                    next_blocks = get_working_hours(next_working_day)
                    if next_blocks:
                        current_datetime = next_blocks[0][0]
                    else:
                        current_datetime = datetime.combine(next_working_day, dt_time(8, 15))
                elif current_block_index is not None and current_block_index < len(blocks) - 1:
                    # Move to next block
                    current_datetime = blocks[current_block_index + 1][0]
                else:
                    # Fallback: move to next day
                    next_working_day = get_next_working_day(current_date)
                    next_blocks = get_working_hours(next_working_day)
                    if next_blocks:
                        current_datetime = next_blocks[0][0]
                    else:
                        current_datetime = datetime.combine(next_working_day, dt_time(8, 15))
                break
        else:
            # No suitable block found today, move to next working day
            next_working_day = get_next_working_day(current_date)
            blocks = get_working_hours(next_working_day)
            if blocks:
                current_datetime = blocks[0][0]
            else:
                current_datetime = datetime.combine(next_working_day, dt_time(8, 15))
    
    return None

def find_available_slot_forward_multiday_with_memory_conflicts(procedure_id, procedure_duration_minutes, start_from_datetime, memory_conflicts):
    """
    Find the earliest available slot for a procedure that may span multiple days
    Considers both database conflicts and in-memory conflicts from current scheduling batch
    """
    Job, Schedule, Procedure, db = get_models()
    
    procedure_duration = minutes_to_timedelta(procedure_duration_minutes)
    search_end_date = start_from_datetime.date() + timedelta(days=30)
    
    # Start from the given start time and work forwards
    current_start_time = start_from_datetime
    
    while current_start_time.date() <= search_end_date:
        remaining_duration = procedure_duration
        schedule_blocks = []
        check_start_time = current_start_time
        
        # Try to build a schedule working forwards
        while remaining_duration > timedelta(0):
            current_date = check_start_time.date()
            
            if not is_working_day(current_date):
                next_working_day = get_next_working_day(current_date)
                blocks = get_working_hours(next_working_day)
                if blocks:
                    check_start_time = blocks[0][0]
                else:
                    check_start_time = datetime.combine(next_working_day, dt_time(8, 15))
                continue
            
            blocks = get_working_hours(current_date)
            if not blocks:
                check_start_time = datetime.combine(current_date + timedelta(days=1), dt_time(8, 15))
                continue
            
            # Process blocks for this day
            for block_start, block_end in blocks:
                if block_start < check_start_time:
                    block_start = max(block_start, check_start_time)
                
                if block_start >= block_end:
                    continue
                
                block_duration = block_end - block_start
                time_to_use = min(remaining_duration, block_duration)
                
                schedule_blocks.append((block_start, block_start + time_to_use))
                remaining_duration -= time_to_use
                check_start_time = block_end
                
                if remaining_duration <= timedelta(0):
                    break
            
            if remaining_duration > timedelta(0):
                # Move to next day
                if current_date == search_end_date:
                    break  # Reached search limit
                next_working_day = get_next_working_day(current_date)
                blocks = get_working_hours(next_working_day)
                if blocks:
                    check_start_time = blocks[0][0]
                else:
                    check_start_time = datetime.combine(next_working_day, dt_time(8, 15))
        
        # Check if we successfully allocated all time
        if remaining_duration <= timedelta(0) and schedule_blocks:
            # Sort blocks chronologically
            schedule_blocks.sort()
            overall_start = schedule_blocks[0][0]
            overall_end = schedule_blocks[-1][1]
            return overall_start, overall_end
        
        # Try again with a later start time
        current_start_time = current_start_time + timedelta(hours=1)
    
    return None

def calculate_single_job_schedule_backward(job, procedures, target_completion_datetime):
    """
    Calculate schedule for a single job working backwards from target completion
    Procedures must be done in sequence order with no gaps between them
    """
    # Sort procedures by sequence in reverse order (last procedure first)
    procedures_sorted = sorted(procedures, key=lambda x: x.sequence, reverse=True)
    job_schedules = []
    current_end_target = target_completion_datetime
    
    for procedure in procedures_sorted:
        procedure_minutes = procedure.procedure_plantime * 60
        
        # Find the exact start time that gives us the required working duration
        # ending exactly at current_end_target
        start_time = find_start_time_for_duration(procedure_minutes, current_end_target)
        
        if not start_time:
            return None  # Cannot schedule this job
        
        schedule_entry = {
            'job_id': job.id,
            'procedure_id': procedure.id,
            'start_datetime': start_time,
            'end_datetime': current_end_target,
            'planned_time': procedure.procedure_plantime,
            'planned_manpower': procedure.procedure_planmanpower
        }
        
        job_schedules.append(schedule_entry)
        
        # Next procedure (earlier in sequence) must end exactly when this one starts
        current_end_target = start_time
    
    # Reverse the list to get chronological order (first procedure first)
    return list(reversed(job_schedules))

def calculate_job_schedule_forward(job, procedures, earliest_start_datetime):
    """
    Calculate schedule for a job working forward from an earliest start time
    Used for lower priority jobs that need to wait
    """
    procedures_sorted = sorted(procedures, key=lambda x: x.sequence)
    job_schedules = []
    current_start = earliest_start_datetime
    
    for procedure in procedures_sorted:
        # Check if procedure duration exceeds largest single working block (4.75 hours = 285 minutes)
        # This accounts for the lunch break - procedures > 4.75h need multi-day scheduling  
        largest_single_block_minutes = 4.75 * 60  # 285 minutes
        procedure_minutes = procedure.procedure_plantime * 60
        
        if procedure_minutes > largest_single_block_minutes:
            # Use multi-day scheduling for procedures that can't fit in a single block
            slot = find_available_slot_forward_multiday(
                procedure.id,
                procedure_minutes,
                current_start
            )
        else:
            # Use single-day scheduling for shorter procedures
            slot = find_available_slot_forward(
                procedure.id,
                procedure_minutes,
                current_start
            )
        
        if not slot:
            return None
        
        start_time, end_time = slot
        schedule_entry = {
            'job_id': job.id,
            'procedure_id': procedure.id,
            'start_datetime': start_time,
            'end_datetime': end_time,
            'planned_time': procedure.procedure_plantime,
            'planned_manpower': procedure.procedure_planmanpower
        }
        
        job_schedules.append(schedule_entry)
        current_start = end_time
    
    return job_schedules

def handle_same_deadline_jobs(jobs, procedures, target_completion_datetime):
    """
    Handle multiple jobs with the same deadline using backward scheduling
    Each job is scheduled to complete by the target completion time
    """
    Job, Schedule, Procedure, db = get_models()
    
    # Sort jobs by ID (priority order) 
    jobs_sorted = sorted(jobs, key=lambda x: x.id)
    procedures_sorted = sorted(procedures, key=lambda x: x.sequence)
    all_schedules = []
    
    # Schedule each job individually using backward scheduling
    # Higher priority jobs (lower ID) get scheduled first and claim their optimal slots
    for job in jobs_sorted:
        job_schedules = calculate_single_job_schedule_backward(job, procedures_sorted, target_completion_datetime)
        
        if not job_schedules:
            # If backward scheduling fails, try forward scheduling from a reasonable start time
            # Calculate total duration needed for this job
            job_duration_minutes = sum(proc.procedure_plantime * 60 for proc in procedures_sorted)
            job_start_time = find_start_time_for_duration(job_duration_minutes, target_completion_datetime)
            
            if job_start_time:
                job_schedules = calculate_job_schedule_forward(job, procedures_sorted, job_start_time)
        
        if job_schedules:
            # Check for conflicts with already scheduled jobs
            conflicts_found = False
            for schedule_data in job_schedules:
                # Check for conflicts with existing schedules for the same procedure
                existing_conflicts = Schedule.query.filter(
                    Schedule.procedure_id == schedule_data['procedure_id'],
                    Schedule.start_datetime < schedule_data['end_datetime'],
                    Schedule.end_datetime > schedule_data['start_datetime']
                ).all()
                
                # Also check conflicts with schedules from current batch
                memory_conflicts = [
                    s for s in all_schedules 
                    if s['procedure_id'] == schedule_data['procedure_id'] and
                    s['start_datetime'] < schedule_data['end_datetime'] and
                    s['end_datetime'] > schedule_data['start_datetime']
                ]
                
                if existing_conflicts or memory_conflicts:
                    conflicts_found = True
                    break
            
            if conflicts_found:
                # Reschedule this job using conflict-aware forward scheduling
                # Find the latest end time of all conflicting procedures
                latest_conflict_end = target_completion_datetime - timedelta(days=30)  # Start from way back
                
                for schedule_data in job_schedules:
                    procedure_id = schedule_data['procedure_id']
                    
                    # Check database conflicts
                    db_conflicts = Schedule.query.filter(
                        Schedule.procedure_id == procedure_id
                    ).all()
                    
                    # Check memory conflicts  
                    memory_conflicts = [
                        s for s in all_schedules 
                        if s['procedure_id'] == procedure_id
                    ]
                    
                    if db_conflicts:
                        latest_conflict_end = max(latest_conflict_end, 
                                                max(c.end_datetime for c in db_conflicts))
                    
                    if memory_conflicts:
                        latest_conflict_end = max(latest_conflict_end,
                                                max(c['end_datetime'] for c in memory_conflicts))
                
                # Try scheduling after all conflicts
                job_schedules = calculate_job_schedule_forward(job, procedures_sorted, latest_conflict_end)
                
                # If this job still extends beyond the deadline, we need to compress the schedule
                if job_schedules and job_schedules[-1]['end_datetime'] > target_completion_datetime:
                    # Try to fit the job by working backwards from deadline with conflict awareness
                    job_schedules = calculate_job_schedule_backward_with_conflicts(
                        job, procedures_sorted, target_completion_datetime, all_schedules
                    )
            
            # Add successful schedules to the batch
            if job_schedules:
                for schedule_data in job_schedules:
                    schedule = Schedule(**schedule_data)
                    db.session.add(schedule)
                    all_schedules.append(schedule_data)
    
    db.session.flush()
    return all_schedules

def regenerate_all_schedules():
    """
    Regenerate all schedules for all jobs based on priority and constraints
    This is the main function called when jobs/procedures are added/edited
    """
    Job, Schedule, Procedure, db = get_models()
    
    # Clear all existing schedules
    Schedule.query.delete()
    db.session.flush()
    
    # Get all jobs grouped by deadline, then by priority (ID)
    jobs = Job.query.order_by(Job.deadline_date, Job.deadline_time, Job.id).all()
    procedures = Procedure.query.order_by(Procedure.sequence).all()
    
    if not jobs or not procedures:
        db.session.commit()
        return []
    
    # Group jobs by deadline
    deadline_groups = {}
    for job in jobs:
        deadline_key = (job.deadline_date, job.deadline_time)
        if deadline_key not in deadline_groups:
            deadline_groups[deadline_key] = []
        deadline_groups[deadline_key].append(job)
    
    # Process each deadline group in chronological order
    for (deadline_date, deadline_time), deadline_jobs in sorted(deadline_groups.items()):
        target_completion = get_completion_target_datetime(deadline_date, deadline_time)
        
        if len(deadline_jobs) == 1:
            # Single job with this deadline - schedule backward
            job_schedules = calculate_single_job_schedule_backward(deadline_jobs[0], procedures, target_completion)
            if job_schedules:
                for schedule_data in job_schedules:
                    schedule = Schedule(**schedule_data)
                    db.session.add(schedule)
                db.session.flush()
        else:
            # Multiple jobs with same deadline - handle priority
            handle_same_deadline_jobs(deadline_jobs, procedures, target_completion)
    
    db.session.commit()
    return Schedule.query.all()

def generate_schedule_for_deadline(deadline_date, deadline_time, procedures):
    """
    Generate schedules for all jobs with the same deadline
    This maintains backward compatibility but now triggers full regeneration
    """
    return regenerate_all_schedules()

def generate_schedule(job, procedures):
    """
    Generate schedule for a single job (backward compatibility)
    This now triggers a full regeneration to maintain constraints
    """
    return regenerate_all_schedules()

def calculate_working_duration_in_span(start_datetime, end_datetime):
    """Calculate actual working hours between two datetimes"""
    total_working_minutes = 0
    current_date = start_datetime.date()
    end_date = end_datetime.date()
    
    while current_date <= end_date:
        working_blocks = get_working_hours(current_date)
        
        for block_start, block_end in working_blocks:
            # Find overlap between this block and our span
            overlap_start = max(block_start, start_datetime)
            overlap_end = min(block_end, end_datetime)
            
            if overlap_start < overlap_end:
                overlap_minutes = (overlap_end - overlap_start).total_seconds() / 60
                total_working_minutes += overlap_minutes
        
        current_date += timedelta(days=1)
    
    return total_working_minutes / 60  # Convert to hours

def find_start_time_for_duration(duration_minutes, target_end_time):
    """
    Find the start time that would result in exactly the specified duration 
    of working time ending at target_end_time, checking for conflicts
    """
    Job, Schedule, Procedure, db = get_models()
    
    remaining_minutes = duration_minutes
    current_end = target_end_time
    search_limit = target_end_time.date() - timedelta(days=60)  # Increased search limit
    working_blocks = []  # Store (start, end) tuples for the schedule
    
    while current_end.date() >= search_limit and remaining_minutes > 0:
        current_date = current_end.date()
        
        if not is_working_day(current_date):
            prev_working_day = get_previous_working_day(current_date)
            blocks = get_working_hours(prev_working_day)
            if blocks:
                current_end = blocks[-1][1]
            continue
        
        blocks = get_working_hours(current_date)
        if not blocks:
            current_end = datetime.combine(current_date - timedelta(days=1), dt_time(17, 0))
            continue
        
        # Work backwards through blocks
        for block_start, block_end in reversed(blocks):
            if block_start >= current_end:
                continue
            
            effective_end = min(block_end, current_end)
            available_time_minutes = (effective_end - block_start).total_seconds() / 60
            
            if available_time_minutes <= 0:
                continue
            
            # Use as much of this block as needed
            time_to_use_minutes = min(available_time_minutes, remaining_minutes)
            block_start_time = effective_end - timedelta(minutes=time_to_use_minutes)
            
            # Store this working block
            working_blocks.append((block_start_time, effective_end))
            remaining_minutes -= time_to_use_minutes
            current_end = block_start_time
            
            if remaining_minutes <= 0:
                break
        else:
            # Move to previous day if we didn't break
            if remaining_minutes > 0:
                prev_working_day = get_previous_working_day(current_date)
                blocks = get_working_hours(prev_working_day)
                if blocks:
                    current_end = blocks[-1][1]
    
    if remaining_minutes > 0:
        return None  # Couldn't allocate enough time
    
    # Return the earliest start time (from the last working block we added)
    if working_blocks:
        working_blocks.sort()
        return working_blocks[0][0]
    
    return None

def calculate_job_schedule_backward_with_conflicts(job, procedures, target_completion_datetime, existing_schedules):
    """
    Calculate schedule for a job working backward from target completion, avoiding conflicts
    """
    # Sort procedures by sequence in reverse order (last procedure first)
    procedures_sorted = sorted(procedures, key=lambda x: x.sequence, reverse=True)
    job_schedules = []
    current_end_target = target_completion_datetime
    
    for procedure in procedures_sorted:
        procedure_minutes = procedure.procedure_plantime * 60
        
        # Find available slot working backwards, considering conflicts
        largest_single_block_minutes = 4.75 * 60  # 285 minutes
        
        # Create a list of all conflicts for this procedure
        all_conflicts = []
        
        # Add database conflicts
        Job, Schedule, Procedure, db = get_models()
        db_conflicts = Schedule.query.filter(
            Schedule.procedure_id == procedure.id
        ).all()
        
        for conflict in db_conflicts:
            all_conflicts.append({
                'procedure_id': conflict.procedure_id,
                'start_datetime': conflict.start_datetime,
                'end_datetime': conflict.end_datetime
            })
        
        # Add memory conflicts
        memory_conflicts = [
            s for s in existing_schedules 
            if s['procedure_id'] == procedure.id
        ]
        all_conflicts.extend(memory_conflicts)
        
        # Try to find slot using backward scheduling with conflict awareness
        slot = None
        search_end_time = current_end_target
        max_attempts = 30  # Prevent infinite loops
        attempts = 0
        
        while not slot and attempts < max_attempts:
            if procedure_minutes > largest_single_block_minutes:
                # Use multi-day backward scheduling
                slot = find_available_slot_backward_multiday_with_conflicts(
                    procedure.id, procedure_minutes, search_end_time, all_conflicts
                )
            else:
                # Use single-day backward scheduling  
                slot = find_available_slot_backward_with_conflicts(
                    procedure.id, procedure_minutes, search_end_time, all_conflicts
                )
            
            if not slot:
                # Move search time earlier and try again
                search_end_time = search_end_time - timedelta(hours=4)
                attempts += 1
        
        if not slot:
            return None  # Cannot schedule this job
        
        start_time, end_time = slot
        schedule_entry = {
            'job_id': job.id,
            'procedure_id': procedure.id,
            'start_datetime': start_time,
            'end_datetime': end_time,
            'planned_time': procedure.procedure_plantime,
            'planned_manpower': procedure.procedure_planmanpower
        }
        
        job_schedules.append(schedule_entry)
        
        # Next procedure (earlier in sequence) must end exactly when this one starts
        current_end_target = start_time
    
    # Reverse the list to get chronological order (first procedure first)
    return list(reversed(job_schedules))

def find_available_slot_backward_with_conflicts(procedure_id, procedure_duration_minutes, target_end_datetime, conflicts):
    """
    Find the latest available slot for a procedure working backwards, considering given conflicts
    """
    Job, Schedule, Procedure, db = get_models()
    
    procedure_duration = minutes_to_timedelta(procedure_duration_minutes)
    current_datetime = target_end_datetime
    search_limit = target_end_datetime.date() - timedelta(days=365)
    
    while current_datetime.date() >= search_limit:
        current_date = current_datetime.date()
        
        if not is_working_day(current_date):
            # Move to previous working day
            prev_working_day = get_previous_working_day(current_date)
            blocks = get_working_hours(prev_working_day)
            if blocks:
                current_datetime = blocks[-1][1]  # End of last block
            else:
                current_datetime = datetime.combine(prev_working_day, dt_time(17, 0))
            continue
        
        blocks = get_working_hours(current_date)
        if not blocks:
            current_datetime = datetime.combine(current_date - timedelta(days=1), dt_time(17, 0))
            continue
        
        # Try blocks from latest to earliest (working backwards)
        for block_start, block_end in reversed(blocks):
            if block_start >= current_datetime:
                continue  # This block is in the future
            
            # Adjust block end to current time if we're in the middle of a block
            effective_end = min(block_end, current_datetime)
            
            # Check available time in this block
            available_time = effective_end - block_start
            
            if available_time >= procedure_duration:
                # Try to place procedure at the end of available time (working backwards)
                candidate_end = effective_end
                candidate_start = candidate_end - procedure_duration
                
                # Ensure it doesn't go before block start
                if candidate_start >= block_start:
                    # Check for conflicts with given conflicts list
                    conflicts_found = [
                        c for c in conflicts 
                        if c['procedure_id'] == procedure_id and
                        c['start_datetime'] < candidate_end and
                        c['end_datetime'] > candidate_start
                    ]
                    
                    if not conflicts_found:
                        return candidate_start, candidate_end
                    else:
                        # Find the earliest start time of conflicting schedules
                        earliest_conflict_start = min(conflict['start_datetime'] for conflict in conflicts_found)
                        current_datetime = earliest_conflict_start
                        break  # Restart search from before this conflict
            else:
                # Not enough time in this block, move to previous block or previous day
                current_block_index = None
                for i, (start, end) in enumerate(blocks):
                    if (start, end) == (block_start, block_end):
                        current_block_index = i
                        break
                
                if current_block_index is not None and current_block_index == 0:  # First block of the day
                    prev_working_day = get_previous_working_day(current_date)
                    prev_blocks = get_working_hours(prev_working_day)
                    if prev_blocks:
                        current_datetime = prev_blocks[-1][1]  # End of last block
                    else:
                        current_datetime = datetime.combine(prev_working_day, dt_time(17, 0))
                elif current_block_index is not None and current_block_index > 0:
                    # Move to previous block
                    current_datetime = blocks[current_block_index - 1][1]
                else:
                    # Fallback: move to previous day
                    prev_working_day = get_previous_working_day(current_date)
                    prev_blocks = get_working_hours(prev_working_day)
                    if prev_blocks:
                        current_datetime = prev_blocks[-1][1]
                    else:
                        current_datetime = datetime.combine(prev_working_day, dt_time(17, 0))
                break
        else:
            # No suitable block found today, move to previous working day
            prev_working_day = get_previous_working_day(current_date)
            blocks = get_working_hours(prev_working_day)
            if blocks:
                current_datetime = blocks[-1][1]
            else:
                current_datetime = datetime.combine(prev_working_day, dt_time(17, 0))
    
    return None

def find_available_slot_backward_multiday_with_conflicts(procedure_id, procedure_duration_minutes, target_end_datetime, conflicts):
    """
    Find the latest available slot for a procedure that may span multiple days, considering conflicts
    """
    Job, Schedule, Procedure, db = get_models()
    
    procedure_duration = minutes_to_timedelta(procedure_duration_minutes)
    search_start_date = target_end_datetime.date() - timedelta(days=30)
    
    # Start from target end time and work backwards
    current_end_time = target_end_datetime
    
    while current_end_time.date() >= search_start_date:
        remaining_duration = procedure_duration
        schedule_blocks = []
        check_end_time = current_end_time
        
        # Try to build a schedule working backwards
        while remaining_duration > timedelta(0):
            current_date = check_end_time.date()
            
            if not is_working_day(current_date):
                prev_working_day = get_previous_working_day(current_date)
                blocks = get_working_hours(prev_working_day)
                if blocks:
                    check_end_time = blocks[-1][1]
                else:
                    check_end_time = datetime.combine(prev_working_day, dt_time(17, 0))
                continue
            
            blocks = get_working_hours(current_date)
            if not blocks:
                check_end_time = datetime.combine(current_date - timedelta(days=1), dt_time(17, 0))
                continue
            
            # Process blocks for this day (from latest to earliest)
            for block_start, block_end in reversed(blocks):
                if block_end > check_end_time:
                    continue
                
                effective_end = min(block_end, check_end_time)
                available_time = effective_end - block_start
                
                if available_time <= timedelta(0):
                    continue
                
                # Use as much of this block as possible
                time_to_use = min(available_time, remaining_duration)
                block_start_time = effective_end - time_to_use
                
                # Check for conflicts in this block
                conflicts_found = [
                    c for c in conflicts 
                    if c['procedure_id'] == procedure_id and
                    c['start_datetime'] < effective_end and
                    c['end_datetime'] > block_start_time
                ]
                
                if conflicts_found:
                    # Find earliest conflict start and try before it
                    earliest_conflict = min(conflict['start_datetime'] for conflict in conflicts_found)
                    if earliest_conflict <= block_start:
                        # Entire block is blocked, try previous block
                        continue
                    else:
                        # Partial block available
                        effective_end = earliest_conflict
                        available_time = effective_end - block_start
                        if available_time <= timedelta(0):
                            continue
                        time_to_use = min(available_time, remaining_duration)
                        block_start_time = effective_end - time_to_use
                
                # Add this block to our schedule
                schedule_blocks.append((block_start_time, block_start_time + time_to_use))
                remaining_duration -= time_to_use
                check_end_time = block_start_time
                
                if remaining_duration <= timedelta(0):
                    break
            
            if remaining_duration > timedelta(0):
                # Move to previous day
                if current_date == search_start_date:
                    break  # Reached search limit
                prev_working_day = get_previous_working_day(current_date)
                blocks = get_working_hours(prev_working_day)
                if blocks:
                    check_end_time = blocks[-1][1]
                else:
                    check_end_time = datetime.combine(prev_working_day, dt_time(17, 0))
        
        # Check if we successfully allocated all time
        if remaining_duration <= timedelta(0) and schedule_blocks:
            # Sort blocks chronologically (earliest first)
            schedule_blocks.sort()
            # Return the start of first block and end of last block
            overall_start = schedule_blocks[0][0]
            overall_end = schedule_blocks[-1][1]
            return overall_start, overall_end
        
        # Try again with an earlier end time
        current_end_time = current_end_time - timedelta(hours=1)
    
    return None