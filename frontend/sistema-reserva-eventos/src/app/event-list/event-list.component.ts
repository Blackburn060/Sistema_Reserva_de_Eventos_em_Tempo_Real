import { Component, OnInit } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { EventCardComponent } from '../event-card/event-card.component';
import { SocketService } from '../socket.service';

@Component({
  selector: 'app-event-list',
  standalone: true,
  imports: [CommonModule, FormsModule, EventCardComponent],
  templateUrl: './event-list.component.html',
  styleUrls: ['./event-list.component.css'],
})
export class EventListComponent implements OnInit {
  events: any[] = [];
  usersOnline: number = 0;
  queue: string[] = [];
  timers: { [key: string]: number } = {};

  constructor(private http: HttpClient, private socketService: SocketService) {}

  ngOnInit(): void {
    this.loadEvents();
    this.setupSocketListeners();
  }

  // Carregar eventos ao iniciar o componente
  loadEvents() {
    this.http.get<any[]>('http://localhost:8000/events').subscribe((data) => {
      this.events = data;
    });
  }

  // Configurar ouvintes para WebSocket
  setupSocketListeners() {
    // Ouvinte para o número de usuários online
    this.socketService.on('online_users', (data) => {
      this.usersOnline = data.count;
    });

    // Adicionar evento recém-criado
    this.socketService.on('event_created', (data) => {
      this.events.push(data);
    });

    // Remover evento deletado
    this.socketService.on('event_deleted', (data) => {
      this.events = this.events.filter((event) => event.id !== data.id);
    });

    // Atualizar fila e timers
    this.socketService.on('queue_update', (data) => {
      this.queue = data.queue;
      this.timers = data.timers; // Receber timers diretamente do backend
    });

    // Atualizar tempo restante para um usuário específico
    this.socketService.on('timer_update', (data) => {
      this.timers[data.sid] = data.time_remaining;
    });
  }
}
