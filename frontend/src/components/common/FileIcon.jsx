import { FileText, FileSpreadsheet, Presentation, File } from 'lucide-react';

const MAP = {
  pdf: { Icon: FileText, cls: 'ft-pdf' },
  docx: { Icon: FileText, cls: 'ft-doc' },
  doc: { Icon: FileText, cls: 'ft-doc' },
  xlsx: { Icon: FileSpreadsheet, cls: 'ft-xls' },
  csv: { Icon: FileSpreadsheet, cls: 'ft-xls' },
  pptx: { Icon: Presentation, cls: 'ft-ppt' },
};

export default function FileIcon({ type, size = 18 }) {
  const { Icon, cls } = MAP[type] ?? { Icon: File, cls: '' };
  return <Icon size={size} className={`file-icon ${cls}`} />;
}
