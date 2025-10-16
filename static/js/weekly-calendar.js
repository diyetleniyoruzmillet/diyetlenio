class WeeklyCalendar {
    constructor(containerId, options = {}) {
        this.container = document.getElementById(containerId);
        this.currentDate = new Date();
        this.selectedDate = null;
        this.selectedTime = null;
        this.availableSlots = options.availableSlots || {};
        this.diyetisyenId = options.diyetisyenId;
        this.onDateTimeSelect = options.onDateTimeSelect || function() {};
        
        this.timeSlots = [
            '09:00', '09:30', '10:00', '10:30', '11:00', '11:30',
            '12:00', '12:30', '13:00', '13:30', '14:00', '14:30',
            '15:00', '15:30', '16:00', '16:30', '17:00', '17:30'
        ];
        
        this.init();
    }
    
    init() {
        this.render();
        this.bindEvents();
    }
    
    render() {
        const today = new Date();
        const tomorrow = new Date(today);
        tomorrow.setDate(today.getDate() + 1);
        
        if (!this.container) {
            console.error('WeeklyCalendar container not found');
            return;
        }

        this.container.innerHTML = `
            <div class="simple-calendar">
                <div class="alert alert-info mb-3">
                    <i class="fas fa-calendar-alt me-2"></i>
                    Randevu tarihi ve saati seçin
                </div>
                
                <div class="row">
                    <div class="col-md-6">
                        <label class="form-label fw-medium">Randevu Tarihi</label>
                        <input type="date" 
                               class="form-control" 
                               id="appointmentDate" 
                               min="${today.toISOString().split('T')[0]}"
                               value="${today.toISOString().split('T')[0]}"
                               required>
                    </div>
                    <div class="col-md-6">
                        <label class="form-label fw-medium">Randevu Saati</label>
                        <select class="form-select" id="appointmentTime" required>
                            <option value="">Saat seçin</option>
                        </select>
                    </div>
                </div>
                
                <div class="available-dates mt-4">
                    <h6 class="mb-3">Yakın Tarihler İçin Hızlı Seçim</h6>
                    <div class="row g-2">
                        <div class="col-6 col-md-3">
                            <button type="button" class="btn btn-outline-primary w-100 quick-date" 
                                    data-date="${today.toISOString().split('T')[0]}">
                                Bugün<br><small>${today.toLocaleDateString('tr-TR', {weekday: 'short', day: 'numeric', month: 'short'})}</small>
                            </button>
                        </div>
                        <div class="col-6 col-md-3">
                            <button type="button" class="btn btn-outline-primary w-100 quick-date" 
                                    data-date="${tomorrow.toISOString().split('T')[0]}">
                                Yarın<br><small>${tomorrow.toLocaleDateString('tr-TR', {weekday: 'short', day: 'numeric', month: 'short'})}</small>
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        `;
        
        // Set today's date as default and update available times
        this.selectedDate = today.toISOString().split('T')[0];
        this.updateAvailableTimes();
    }
    
    bindEvents() {
        // Date input change event
        document.addEventListener('change', (e) => {
            if (e.target.id === 'appointmentDate') {
                this.selectedDate = e.target.value;
                this.updateAvailableTimes();
                this.selectedTime = null; // Reset selected time when date changes
                this.checkDateTimeSelection();
            }
            if (e.target.id === 'appointmentTime') {
                this.selectedTime = e.target.value;
                this.checkDateTimeSelection();
            }
        });
        
        // Quick date selection
        document.addEventListener('click', (e) => {
            if (e.target.classList.contains('quick-date') || e.target.closest('.quick-date')) {
                const quickDateBtn = e.target.classList.contains('quick-date') ? e.target : e.target.closest('.quick-date');
                const date = quickDateBtn.dataset.date;
                document.getElementById('appointmentDate').value = date;
                this.selectedDate = date;
                this.updateAvailableTimes();
                this.selectedTime = null; // Reset selected time when date changes
                this.checkDateTimeSelection();
                
                // Visual feedback
                document.querySelectorAll('.quick-date').forEach(btn => btn.classList.remove('active'));
                quickDateBtn.classList.add('active');
            }
        });
    }
    
    updateAvailableTimes() {
        const timeSelect = document.getElementById('appointmentTime');
        if (!timeSelect) return;
        
        // Clear existing options
        timeSelect.innerHTML = '<option value="">Saat seçin</option>';
        
        const now = new Date();
        const selectedDate = new Date(this.selectedDate);
        const isToday = selectedDate.toDateString() === now.toDateString();
        
        let availableTimes = this.timeSlots;
        
        // If today is selected, filter out past times
        if (isToday) {
            const currentHour = now.getHours();
            const currentMinute = now.getMinutes();
            
            availableTimes = this.timeSlots.filter(timeSlot => {
                const [hour, minute] = timeSlot.split(':').map(Number);
                const slotTime = hour * 60 + minute;
                const currentTime = currentHour * 60 + currentMinute;
                
                // Add 30 minutes buffer for preparation
                return slotTime > (currentTime + 30);
            });
        }
        
        // Add available times to select
        availableTimes.forEach(time => {
            const option = document.createElement('option');
            option.value = time;
            option.textContent = time;
            timeSelect.appendChild(option);
        });
        
        // Show message if no times available
        if (availableTimes.length === 0) {
            const option = document.createElement('option');
            option.value = '';
            option.textContent = isToday ? 'Bu gün için müsait saat yok' : 'Müsait saat yok';
            option.disabled = true;
            timeSelect.appendChild(option);
        }
    }
    
    checkDateTimeSelection() {
        if (this.selectedDate && this.selectedTime) {
            // Create datetime string
            const datetime = `${this.selectedDate}T${this.selectedTime}:00`;
            
            // Call the callback if it exists
            if (typeof this.onDateTimeSelect === 'function') {
                this.onDateTimeSelect({
                    datetime: datetime,
                    date: this.selectedDate,
                    time: this.selectedTime
                });
            }
        }
    }
}