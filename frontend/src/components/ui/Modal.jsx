function Modal({ open, title, onClose, children, actions, maxWidth = "860px" }) {
  if (!open) return null;

  return (
    <div className="modal-overlay" onMouseDown={onClose}>
      <div
        className="modal-card"
        style={{ maxWidth }}
        onMouseDown={(event) => event.stopPropagation()}
      >
        <header className="modal-head">
          <h3>{title}</h3>
          <button type="button" className="icon-btn" onClick={onClose} aria-label="Close">
            ×
          </button>
        </header>
        <div className="modal-body">{children}</div>
        {actions ? <footer className="modal-foot">{actions}</footer> : null}
      </div>
    </div>
  );
}

export default Modal;
