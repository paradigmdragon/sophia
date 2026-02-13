export function SkillsPanel() {
    return (
        <div className="p-4 text-gray-400 text-sm">
            <h3 className="font-bold mb-2">Available Skills</h3>
            <ul className="list-disc pl-4 space-y-1">
                <li>memory.append</li>
                <li>workspace.read_file</li>
                <li>workspace.write_file</li>
            </ul>
        </div>
    );
}
