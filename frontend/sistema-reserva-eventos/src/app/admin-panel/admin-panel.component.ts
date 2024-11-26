import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { HttpClient } from '@angular/common/http';

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

  constructor(private http: HttpClient) {}

  ngOnInit(): void {
    this.loadEvents();
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

  loadEvents() {
    this.http.get<any[]>('http://localhost:8000/events').subscribe((data) => {
      this.events = data;
    });
  }
}
