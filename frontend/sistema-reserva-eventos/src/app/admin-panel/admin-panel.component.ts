import { Component, OnInit } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';

@Component({
  selector: 'app-admin-panel',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './admin-panel.component.html',
  styleUrls: ['./admin-panel.component.css'],
})
export class AdminPanelComponent implements OnInit {
  events: any[] = [];
  newEvent = { name: '', slots: 0, date: '' };
  maxUsers = 3;
  choiceTimeout = 30;
  reservationTimeout = 120;

  constructor(private http: HttpClient) {}

  ngOnInit(): void {
    this.loadEvents();
    this.loadSettings();
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

  saveSettings() {
    const settings = {
      maxUsers: this.maxUsers,
      choiceTimeout: this.choiceTimeout,
      reservationTimeout: this.reservationTimeout,
    };
    this.http.post('http://localhost:8000/settings', settings).subscribe(() => {
      alert('Configurações atualizadas!');
    });
  }

  createEvent() {
    if (!this.newEvent.name || !this.newEvent.slots || !this.newEvent.date) {
      alert('Por favor, preencha todos os campos!');
      return;
    }

    this.http.post('http://localhost:8000/events', this.newEvent).subscribe(() => {
      this.loadEvents();
      this.newEvent = { name: '', slots: 0, date: '' };
    });
  }

  deleteEvent(eventId: number) {
    this.http.delete(`http://localhost:8000/events/${eventId}`).subscribe(() => {
      this.loadEvents();
    });
  }
}
