"""
Time tracking utilities for Azure Egress Management.
"""
import time
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class TimeTracker:
    """Simple utility to track execution time of project phases."""
    
    def __init__(self, tracking_file: str = None):
        """
        Initialize the time tracker.
        
        Args:
            tracking_file: Path to store timing data (None for no persistence)
        """
        self.tracking_file = tracking_file or str(
            Path(__file__).parent.parent.parent / "data" / "time_tracking.json"
        )
        self.phases: Dict[str, Dict[str, Any]] = {}
        self._load_existing_data()
        
    def _load_existing_data(self):
        """Load existing timing data if available."""
        try:
            if Path(self.tracking_file).exists():
                with open(self.tracking_file, 'r') as f:
                    self.phases = json.load(f)
        except Exception as ex:
            logger.warning(f"Could not load timing data: {ex}")
    
    def start_phase(self, phase_id: str, description: str = ""):
        """
        Start timing a phase.
        
        Args:
            phase_id: Unique identifier for the phase
            description: Optional phase description
        """
        self.phases[phase_id] = {
            "start_time": datetime.now().isoformat(),
            "description": description,
            "status": "in_progress"
        }
        self._save()
        
    def end_phase(self, phase_id: str, status: str = "completed"):
        """
        End timing a phase.
        
        Args:
            phase_id: Unique identifier for the phase
            status: Final status (completed/failed/etc)
            
        Returns:
            Dict with timing information or None if phase not found
        """
        if phase_id not in self.phases:
            logger.warning(f"Phase {phase_id} not found in tracking data")
            return None
            
        phase = self.phases[phase_id]
        phase["end_time"] = datetime.now().isoformat()
        phase["status"] = status
        
        # Calculate duration if possible
        try:
            start = datetime.fromisoformat(phase["start_time"])
            end = datetime.fromisoformat(phase["end_time"])
            duration_seconds = (end - start).total_seconds()
            phase["duration_seconds"] = duration_seconds
            phase["duration_formatted"] = self._format_duration(duration_seconds)
        except Exception as ex:
            logger.warning(f"Could not calculate duration: {ex}")
            
        self._save()
        return phase
    
    def _format_duration(self, seconds: float) -> str:
        """
        Format duration in seconds to a readable string.
        
        Args:
            seconds: Duration in seconds
            
        Returns:
            Formatted duration string (e.g., "2h 30m 15s")
        """
        hours, remainder = divmod(seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        
        parts = []
        if hours > 0:
            parts.append(f"{int(hours)}h")
        if minutes > 0 or hours > 0:
            parts.append(f"{int(minutes)}m")
        parts.append(f"{int(seconds)}s")
        
        return " ".join(parts)
        
    def _save(self):
        """Save timing data to file."""
        if not self.tracking_file:
            return
            
        try:
            # Ensure directory exists
            Path(self.tracking_file).parent.mkdir(parents=True, exist_ok=True)
            
            with open(self.tracking_file, 'w') as f:
                json.dump(self.phases, f, indent=2)
        except Exception as ex:
            logger.warning(f"Could not save timing data: {ex}")
    
    def get_phase_summary(self) -> Dict[str, Any]:
        """
        Get a summary of all phase timings.
        
        Returns:
            Dict with timing summaries
        """
        total_duration = 0
        completed_phases = 0
        
        for phase_id, phase in self.phases.items():
            if "duration_seconds" in phase:
                total_duration += phase["duration_seconds"]
                if phase["status"] == "completed":
                    completed_phases += 1
        
        return {
            "total_phases": len(self.phases),
            "completed_phases": completed_phases,
            "total_duration_seconds": total_duration,
            "total_duration_formatted": self._format_duration(total_duration),
            "phases": self.phases
        }
