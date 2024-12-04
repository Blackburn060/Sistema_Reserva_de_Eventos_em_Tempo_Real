import { Component, OnInit } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { EventCardComponent } from '../event-card/event-card.component';
import { ReservationModalComponent } from '../reservation-modal/reservation-modal.component';
import { SocketService } from '../socket.service';
import { MatIconModule } from '@angular/material/icon';

@Component({
  selector: 'app-event-list',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    EventCardComponent,
    ReservationModalComponent,
    MatIconModule,
  ],
  templateUrl: './event-list.component.html',
  styleUrls: ['./event-list.component.css'],
})
export class EventListComponent implements OnInit {
  events: any[] = [];
  usersOnline: number = 0;
  queue: string[] = [];
  timers: { [key: string]: number } = {};
  selectedEvent: any = null;
  maxUsers: number = 3;
  choiceTimeout: number = 30;
  reservationTimeout: number = 120;

  constructor(private http: HttpClient, private socketService: SocketService) {}

  ngOnInit(): void {
    this.loadEvents();
    this.loadSettings();
    this.setupSocketListeners();
  }

  loadEvents() {
    this.http.get<any[]>('http://localhost:8000/events').subscribe((data) => {
      this.events = data;
    });
  }

  loadSettings() {
    this.http.get<any>('http://localhost:8000/settings').subscribe((settings) => {
      this.maxUsers = settings.maxUsers;
      this.choiceTimeout = settings.choiceTimeout;
      this.reservationTimeout = settings.reservationTimeout;
    });
  }

  setupSocketListeners() {
    this.socketService.on('online_users', (data) => {
      this.usersOnline = data.count;
    });

    this.socketService.on('event_created', (data) => {
      this.events.push(data);
    });

    this.socketService.on('event_deleted', (data) => {
      this.events = this.events.filter((event) => event.id !== data.id);
    });

    this.socketService.on('queue_update', (data) => {
      this.queue = data.queue;
      this.timers = data.timers;
    });

    this.socketService.on('timer_update', (data) => {
      this.timers[data.sid] = data.time_remaining;
    });

    this.socketService.on('event_updated', (data) => {
      this.updateEventSlots(data);
    });

    this.socketService.on('reservation_confirmed', (data) => {
      console.log(`Reserva confirmada para usuário ${data.user} no evento ${data.eventId}`);
    });

    this.socketService.on('reservation_timeout', (data) => {
      if (this.selectedEvent && this.selectedEvent.id === data.eventId) {
        this.selectedEvent = null;
      }
    });

    this.socketService.on('error', (data) => {
      console.error(data.message);
      alert(data.message);
    });
  }

  onReserve(event: any) {
    this.socketService.emit('reserve', { eventId: event.id }, (response: any) => {
      if (response.success) {
        this.selectedEvent = { ...event, reservationTimeout: this.reservationTimeout };
      } else {
        alert(response.message);
      }
    });
  }

  onConfirmReservation(userData: { name: string; phone: string }) {
    if (this.selectedEvent) {
      this.socketService.emit('confirm_reservation', {
        eventId: this.selectedEvent.id,
        name: userData.name,
        phone: userData.phone,
      });
      this.selectedEvent = null;
    }
  }

  onCancelReservation() {
    if (this.selectedEvent) {
      this.socketService.emit('cancel_reservation', {
        eventId: this.selectedEvent.id,
      });
      this.selectedEvent = null;
    }
  }

  onCloseModal() {
    if (this.selectedEvent) {
      this.onCancelReservation();
    }
  }

  updateEventSlots(eventData: any) {
    const updatedEvent = this.events.find((e) => e.id === eventData.id);
    if (updatedEvent) {
      updatedEvent.slots = eventData.slots;
    }
  }
}
