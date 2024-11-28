import { Component, OnInit } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { EventCardComponent } from '../event-card/event-card.component';
import { ReservationModalComponent } from '../reservation-modal/reservation-modal.component';
import { SocketService } from '../socket.service';

@Component({
  selector: 'app-event-list',
  standalone: true,
  imports: [CommonModule, FormsModule, EventCardComponent, ReservationModalComponent],
  templateUrl: './event-list.component.html',
  styleUrls: ['./event-list.component.css'],
})
export class EventListComponent implements OnInit {
  events: any[] = [];
  usersOnline: number = 0;
  queue: string[] = [];
  timers: { [key: string]: number } = {};
  selectedEvent: any = null;
  maxUsers: number = 3;  // Valor padrão
  choiceTimeout: number = 30;  // Valor padrão

  constructor(private http: HttpClient, private socketService: SocketService) {}

  ngOnInit(): void {
    this.loadEvents();
    this.loadSettings();
    this.setupSocketListeners();
  }

  // Carrega os eventos do backend
  loadEvents() {
    this.http.get<any[]>('http://localhost:8000/events').subscribe((data) => {
      this.events = data;
    });
  }

  // Carrega as configurações de Máx. Usuários e Tempo de Escolha
  loadSettings() {
    this.http.get<any>('http://localhost:8000/settings').subscribe((settings) => {
      this.maxUsers = settings.maxUsers;  // Ajusta a configuração carregada
      this.choiceTimeout = settings.choiceTimeout;  // Ajusta o tempo de escolha
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
  }

  onReserve(event: any) {
    this.selectedEvent = event;
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

  onCloseModal() {
    this.selectedEvent = null;
  }
}
