from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util
from .const import DOMAIN
from .coordinator import MinRenovasjonCoordinator
from datetime import datetime, time, timedelta
import logging

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the Min Renovasjon calendar."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([MinRenovasjonCalendar(coordinator)], True)

class MinRenovasjonCalendar(CoordinatorEntity, CalendarEntity):
    """Min Renovasjon Calendar."""

    def __init__(self, coordinator: MinRenovasjonCoordinator):
        """Initialize Min Renovasjon Calendar."""
        super().__init__(coordinator)
        self._attr_name = "Min Renovasjon Collection"
        
        # Safe unique_id generation with fallback
        try:
            entry_id = coordinator.config_entry.entry_id
        except AttributeError:
            entry_id = "min_renovasjon_unknown"
        self._attr_unique_id = f"{entry_id}_calendar"
        
        # Cache logic is removed/simplified to ensure grouping always works on fresh data
        # (Coordinator handles the API caching anyway)

    @property
    def event(self):
        """Return the next upcoming event (merged if multiple on same day)."""
        if not self.coordinator.data:
            return None

        # 1. Find the absolute earliest date across ALL fractions
        earliest_date = None
        
        for fraction_data in self.coordinator.data.values():
            if not fraction_data or len(fraction_data) < 4:
                continue
            
            # Check next and next-next date
            next_dates = [d for d in [fraction_data[3], fraction_data[4] if len(fraction_data) >= 5 else None] if d]
            
            for date_obj in next_dates:
                if earliest_date is None or date_obj < earliest_date:
                    earliest_date = date_obj

        if earliest_date is None:
            return None

        # 2. Find ALL fractions that occur on this earliest date (ignoring time)
        fractions_on_day = []
        target_date_key = earliest_date.date()

        for fraction_data in self.coordinator.data.values():
            if not fraction_data or len(fraction_data) < 4:
                continue
                
            fraction_name = fraction_data[1]
            # Check dates again
            next_dates = [d for d in [fraction_data[3], fraction_data[4] if len(fraction_data) >= 5 else None] if d]
            
            for date_obj in next_dates:
                if date_obj.date() == target_date_key:
                    fractions_on_day.append(fraction_name)
        
        # Remove duplicates and sort alphabetically for consistent text
        fractions_on_day = sorted(list(set(fractions_on_day)))
        combined_summary = " og ".join(fractions_on_day)

        # 3. Create the Event object
        try:
            start_date_obj = target_date_key
            end_date_obj = start_date_obj + timedelta(days=1)

            event = CalendarEvent(
                summary=combined_summary,
                start=start_date_obj,
                end=end_date_obj,
                description=f"Tømming av {combined_summary}",
            )
            return event

        except (AttributeError, TypeError, ValueError) as e:
            _LOGGER.warning(f"Error processing calendar event dates: {e}")
            return None

    async def async_get_events(self, hass, start_date, end_date):
        """Return events within a start and end date (Merged by date)."""
        if not self.coordinator.data:
            return []

        # Dictionary to group fractions by date: { date_obj: ["Restavfall", "Papir"] }
        grouped_events = {}

        # 1. Collect all events and group them by date
        for fraction_data in self.coordinator.data.values():
            if not fraction_data or len(fraction_data) < 4:
                continue

            fraction_name = fraction_data[1]
            
            # Get next and next-next pickup dates
            dates_to_check = [fraction_data[3]]
            if len(fraction_data) >= 5:
                dates_to_check.append(fraction_data[4])

            for date_obj in dates_to_check:
                if date_obj is None or not isinstance(date_obj, datetime):
                    continue

                # Use date object as key (strips time)
                date_key = date_obj.date()
                
                # Filter by requested range immediately
                if start_date.date() <= date_key < end_date.date():
                    if date_key not in grouped_events:
                        grouped_events[date_key] = []
                    grouped_events[date_key].append(fraction_name)

        # 2. Create CalendarEvent objects from the grouped data
        events = []
        for date_key, fraction_list in grouped_events.items():
            # Remove duplicates and sort
            unique_fractions = sorted(list(set(fraction_list)))
            combined_summary = " og ".join(unique_fractions)
            
            event_start = date_key
            event_end = date_key + timedelta(days=1)

            events.append(
                CalendarEvent(
                    summary=combined_summary,
                    start=event_start,
                    end=event_end,
                    description=f"Tømming av {combined_summary}",
                )
            )
        
        return events
