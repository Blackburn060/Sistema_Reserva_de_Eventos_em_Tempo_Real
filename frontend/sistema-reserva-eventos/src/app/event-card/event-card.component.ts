import { Component, Input, Output, EventEmitter } from '@angular/core';
import { MatCardModule } from '@angular/material/card';
import { DatePipe } from '@angular/common'; // Importando o DatePipe para corrigir o erro do pipe

@Component({
  selector: 'app-event-card',
  standalone: true,
  imports: [MatCardModule, DatePipe], // Incluindo o DatePipe
  templateUrl: './event-card.component.html',
  styleUrls: ['./event-card.component.css'],
})
export class EventCardComponent {
  @Input() event: any;
  @Output() reserve = new EventEmitter<any>();

  onReserve() {
    this.reserve.emit(this.event);
  }
}
