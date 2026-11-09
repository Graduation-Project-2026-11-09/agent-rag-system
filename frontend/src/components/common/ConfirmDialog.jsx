import Modal from './Modal';

export default function ConfirmDialog({ open, title, message, confirmLabel = '実行する', danger, onConfirm, onCancel }) {
  return (
    <Modal
      open={open}
      title={title}
      onClose={onCancel}
      size="sm"
      footer={
        <>
          <button className="btn" onClick={onCancel}>キャンセル</button>
          <button className={`btn ${danger ? 'btn-danger' : 'btn-primary'}`} onClick={onConfirm}>{confirmLabel}</button>
        </>
      }
    >
      <p className="pre-wrap">{message}</p>
    </Modal>
  );
}
