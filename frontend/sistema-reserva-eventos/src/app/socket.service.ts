import { Injectable } from '@angular/core';
import { io, Socket } from 'socket.io-client';

@Injectable({
  providedIn: 'root'
})
export class SocketService {
  private socket: Socket;

  constructor() {
    this.socket = io('http://localhost:8000', {
      transports: ['websocket'],
      path: '/socket.io',
      reconnection: true,
      reconnectionAttempts: 5,
      reconnectionDelay: 1000,
    });

    this.socket.on('connect_error', (error) => {
      console.error('Erro de conexão com o WebSocket:', error);
    });

    this.socket.on('disconnect', (reason) => {
      console.warn('Socket desconectado:', reason);
    });
  }

  emit(eventName: string, data: any): void {
    this.socket.emit(eventName, data);
  }

  on(eventName: string, callback: (data: any) => void): void {
    this.socket.on(eventName, callback);
  }

  disconnect(): void {
    this.socket.disconnect();
  }

  reconnect(): void {
    if (!this.socket.connected) {
      this.socket.connect();
    }
  }
}
