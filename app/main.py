# This is the main entry point for the application.
node_map  = {}

head_node = Node(
    NodeId="head",
    ParentNodeId=None,
    NodeHash="hash1",
    GitCommitSHA="commit1",
    NodePrompt="Initial prompt",
    NodeRawResponse="Initial response"
)
node_map[head_node.NodeId] = head_node

