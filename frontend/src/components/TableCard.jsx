import { QRCodeSVG } from "qrcode.react";

export default function TableCard({ table, onCopyQR, onDelete }) {
  const menuUrl = `${window.location.origin}/menu/${table.qr_token}`;
  
  return (
    <div className="card bg-base-100 shadow-xl">
      <div className="card-body">
        <div className="flex items-center justify-between">
          <h2 className="card-title">Masa {table.table_number}</h2>
          {table.check_requested && (
            <div className="badge badge-warning gap-2">
              💳 Hesap İstiyor
            </div>
          )}
        </div>
        
        {/* QR Code */}
        <div className="flex justify-center my-4 bg-white p-4 rounded-lg">
          <QRCodeSVG 
            value={menuUrl} 
            size={150}
            level="H"
            includeMargin={true}
          />
        </div>
        
        {/* Table Info */}
        <div className="space-y-2 text-sm">
          {table.active_orders_count > 0 ? (
            <>
              <div className="flex justify-between">
                <span className="opacity-70">Aktif Sipariş:</span>
                <span className="font-semibold">{table.active_orders_count}</span>
              </div>
              <div className="flex justify-between">
                <span className="opacity-70">Güncel Hesap:</span>
                <span className="font-bold text-lg text-primary">
                  {table.current_total.toFixed(2)} ₺
                </span>
              </div>
            </>
          ) : (
            <div className="text-center opacity-50 py-2">
              Aktif sipariş yok
            </div>
          )}
        </div>
        
        <div className="card-actions justify-end mt-2">
          <button
            className="btn btn-sm btn-primary"
            onClick={() => onCopyQR(table.qr_token)}
          >
            Linki Kopyala
          </button>
          <button
            className="btn btn-sm btn-error"
            onClick={() => onDelete(table.id)}
          >
            Sil
          </button>
        </div>
      </div>
    </div>
  );
}
